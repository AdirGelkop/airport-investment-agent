"""Download public aviation data and save it as small files in data/cache/.

    python data_sources.py --refresh    download everything again
    python data_sources.py              print a quick sanity check of the cached data
    python data_sources.py --opensky    also fetch the last 7 days of Anchorage departures
"""
from __future__ import annotations

import io
import json
import os
import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The macOS system Python prints a harmless SSL warning when `requests` is imported
warnings.filterwarnings("ignore", message=".*OpenSSL.*")

import pandas as pd
import requests
from dotenv import load_dotenv

import config

load_dotenv()

CACHE_DIR = Path(__file__).parent / "data" / "cache"
OPENSKY_DIR = CACHE_DIR / "opensky"
CACHE_FILES = {
    "monthly": CACHE_DIR / "bts_monthly.csv",
    "base2019": CACHE_DIR / "bts_2019.csv",
    "airports": CACHE_DIR / "airports_us.csv",
    "coords": CACHE_DIR / "airport_coords_world.csv",
}


# ---------- BTS T-100 (passengers, seats, departures per airport and month) ----------

def query_bts(params: dict) -> list[dict]:
    """Run a query on the BTS open-data API, reading all result pages."""
    rows, offset, page_size = [], 0, 50_000
    while True:
        page = requests.get(config.BTS_ENDPOINT, timeout=120,
                            params={**params, "$limit": page_size, "$offset": offset})
        page.raise_for_status()
        batch = page.json()
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        offset += page_size


def fetch_bts_monthly(months: int = 24) -> pd.DataFrame:
    """Monthly totals per US origin airport for the latest `months` months."""
    latest = pd.Timestamp(query_bts({"$select": "max(reporting_month) as m"})[0]["m"])
    start = latest - pd.DateOffset(months=months - 1)
    rows = query_bts({
        "$select": "origin_airport_code as airport, reporting_month as month, "
                   "total_departures as deps, total_passengers as pax, total_seats as seats, "
                   "total_distance_flight_sm as avg_dist, domestic_passengers as dom_pax, "
                   "total_freight_lbs as freight_lbs",
        "$where": f"reporting_month >= '{start:%Y-%m-%d}T00:00:00'",
        "$order": "reporting_month, origin_airport_code",
    })
    df = pd.DataFrame(rows)
    numbers = ["deps", "pax", "seats", "avg_dist", "dom_pax", "freight_lbs"]
    df[numbers] = df[numbers].apply(pd.to_numeric, errors="coerce").fillna(0)
    df["month"] = pd.to_datetime(df["month"])

    # avg_dist is an average per flight, so keep distance x departures to re-average later
    df["dist_x_deps"] = df["avg_dist"] * df["deps"]
    totals = ["deps", "pax", "seats", "dist_x_deps", "dom_pax", "freight_lbs"]
    return df.groupby(["airport", "month"], as_index=False)[totals].sum()


def fetch_bts_2019() -> pd.DataFrame:
    """Pre-pandemic baseline: total 2019 passengers per origin airport."""
    rows = query_bts({
        "$select": "origin_airport_code as airport, sum(total_passengers) as pax_2019",
        "$where": "year = '2019'",
        "$group": "origin_airport_code",
    })
    df = pd.DataFrame(rows)
    df["pax_2019"] = pd.to_numeric(df["pax_2019"], errors="coerce")
    return df


# ---------- OurAirports (location, state, runways) ----------

def read_csv_url(url: str) -> pd.DataFrame:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    return pd.read_csv(io.StringIO(response.text), low_memory=False)


def fetch_airports() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (US airports with runway count, coordinates of airports worldwide by ICAO code)."""
    airports = read_csv_url(config.OURAIRPORTS_AIRPORTS)
    runways = read_csv_url(config.OURAIRPORTS_RUNWAYS)

    # Count open runways long enough for airliners
    open_runways = runways[(runways["closed"] == 0) & (runways["length_ft"] >= config.MIN_RUNWAY_LENGTH_FT)]
    runway_count = open_runways.groupby("airport_ident").size().rename("runways")

    us = airports[(airports["iso_country"] == "US") & airports["iata_code"].notna()].copy()
    us["state"] = us["iso_region"].str.replace("US-", "")
    us["icao"] = us["gps_code"].fillna(us["ident"])
    us = us.rename(columns={"iata_code": "code", "municipality": "city",
                            "latitude_deg": "lat", "longitude_deg": "lon"})
    us = us.merge(runway_count, left_on="ident", right_index=True, how="left")

    # If an IATA code appears twice, keep the larger airport
    size_order = {"large_airport": 0, "medium_airport": 1, "small_airport": 2}
    us["size_order"] = us["type"].map(size_order).fillna(9)
    us = us.sort_values("size_order").drop_duplicates("code")
    us = us[["code", "icao", "ident", "name", "city", "state", "lat", "lon", "type", "runways"]]

    # Worldwide coordinates, looked up by ident or GPS code (used for flight distances)
    world = airports[airports["type"].isin(size_order)]
    by_ident = world[["ident", "latitude_deg", "longitude_deg"]].rename(columns={"ident": "icao"})
    by_gps = world[world["gps_code"].notna()][["gps_code", "latitude_deg", "longitude_deg"]]
    by_gps = by_gps.rename(columns={"gps_code": "icao"})
    coords = pd.concat([by_ident, by_gps]).drop_duplicates("icao")
    coords = coords.rename(columns={"latitude_deg": "lat", "longitude_deg": "lon"})
    return us, coords


# ---------- OpenSky (observed flights with destinations) ----------

def get_opensky_token() -> str | None:
    """OAuth2 token from OpenSky, or None when no credentials are set in .env."""
    client_id, secret = os.getenv("OPENSKY_CLIENT_ID"), os.getenv("OPENSKY_CLIENT_SECRET")
    if not client_id or not secret:
        return None
    response = requests.post(config.OPENSKY_TOKEN_URL, timeout=30, data={
        "grant_type": "client_credentials", "client_id": client_id, "client_secret": secret})
    response.raise_for_status()
    return response.json()["access_token"]


def load_or_fetch_day(icao: str, day, token: str | None, notes: list[str]) -> list[dict] | None:
    """Departures for one UTC day: from the cache, else from OpenSky. None if unavailable."""
    cache_file = OPENSKY_DIR / f"{icao}_{day}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())
    if not token:
        return None

    begin = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
    response = requests.get(f"{config.OPENSKY_API}/flights/departure", timeout=60,
                            headers={"Authorization": f"Bearer {token}"},
                            params={"airport": icao, "begin": begin, "end": begin + 86_399})
    if response.status_code == 404:  # OpenSky answers 404 when there are no flights
        flights = []
    elif response.ok:
        flights = response.json()
    else:
        notes.append(f"OpenSky returned HTTP {response.status_code} for {day}; day skipped.")
        return None
    cache_file.write_text(json.dumps(flights))
    return flights


def fetch_opensky_departures(icao: str, days: int = config.OPENSKY_DAYS) -> tuple[list[dict], list[str], list[str]]:
    """Departures from `icao` over the last `days` full UTC days.
    OpenSky processes flights overnight, so the window ends 2 days ago.
    Returns (flights, days used, notes)."""
    OPENSKY_DIR.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    try:
        token = get_opensky_token()
    except requests.RequestException as error:
        token = None
        notes.append(f"OpenSky login failed ({error}); using cached days only.")

    today = datetime.now(timezone.utc).date()
    flights, days_used = [], []
    for offset in range(2, 2 + days):
        day = today - timedelta(days=offset)
        day_flights = load_or_fetch_day(icao, day, token, notes)
        if day_flights is not None:
            flights += day_flights
            days_used.append(str(day))

    if not days_used:
        # Nothing for the recent window (no credentials): use the newest cached days instead
        for cache_file in sorted(OPENSKY_DIR.glob(f"{icao}_*.json"))[-days:]:
            flights += json.loads(cache_file.read_text())
            days_used.append(cache_file.stem.split("_")[1])
        if days_used:
            notes.append("No OpenSky credentials: using the most recent cached days.")
        else:
            notes.append("No OpenSky credentials and no cached data for this airport.")
    elif len(days_used) < days:
        notes.append(f"Only {len(days_used)} of {days} requested days were available.")
    return flights, sorted(days_used), notes


# ---------- Cache ----------

def refresh_cache() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print("Downloading BTS T-100 monthly data (last 24 months)...")
    fetch_bts_monthly().to_csv(CACHE_FILES["monthly"], index=False)
    print("Downloading BTS 2019 baseline...")
    fetch_bts_2019().to_csv(CACHE_FILES["base2019"], index=False)
    print("Downloading OurAirports airports and runways...")
    us, coords = fetch_airports()
    us.to_csv(CACHE_FILES["airports"], index=False)
    coords.to_csv(CACHE_FILES["coords"], index=False)
    print("Done. Cache saved in", CACHE_DIR)


def load_all() -> dict[str, pd.DataFrame]:
    """Load the cached data (downloads it first if the cache is missing)."""
    if not all(path.exists() for path in CACHE_FILES.values()):
        refresh_cache()
    data = {name: pd.read_csv(path) for name, path in CACHE_FILES.items()}
    data["monthly"]["month"] = pd.to_datetime(data["monthly"]["month"])
    return data


if __name__ == "__main__":
    if "--refresh" in sys.argv:
        refresh_cache()
    monthly = load_all()["monthly"]
    print(f"\nMonthly rows: {len(monthly):,} | airports: {monthly.airport.nunique():,} | "
          f"months: {monthly.month.min():%Y-%m} .. {monthly.month.max():%Y-%m}")

    last12 = monthly[monthly.month > monthly.month.max() - pd.DateOffset(months=12)]
    totals = last12.groupby("airport")[["pax", "seats", "deps"]].sum()
    totals["load_factor"] = (totals.pax / totals.seats).round(3)
    print("\nSanity check, last 12 months:")
    print(totals.loc[["SFO", "LAX", "SNA", "ANC", "BOS"]])

    if "--opensky" in sys.argv:
        flights, days, notes = fetch_opensky_departures("PANC")
        print(f"\nOpenSky PANC: {len(flights)} departures over days {days} {notes}")
