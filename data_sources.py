"""Fetch public aviation data and cache it as small CSV/JSON files in data/cache/.

Run once to build the cache:   python data_sources.py --refresh
After that the app works offline (except the LLM call and new OpenSky days).
"""
from __future__ import annotations

import io
import json
import os
import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

warnings.filterwarnings("ignore", message=".*OpenSSL.*")  # harmless on macOS system Python

import pandas as pd  # noqa: E402
import requests  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

import config  # noqa: E402

load_dotenv()
CACHE = Path(__file__).parent / "data" / "cache"
OPENSKY_CACHE = CACHE / "opensky"


# ---------------------------------------------------------------- BTS T-100
def _socrata(params: dict) -> List[dict]:
    """Query the BTS Socrata API, paging through results."""
    rows, offset, page = [], 0, 50_000
    while True:
        p = dict(params)
        p.update({"$limit": page, "$offset": offset})
        r = requests.get(config.BTS_ENDPOINT, params=p, timeout=120)
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        if len(batch) < page:
            return rows
        offset += page


def fetch_bts_monthly(months: int = 24) -> pd.DataFrame:
    """Monthly departures / passengers / seats per US origin airport for the last `months` months."""
    latest = _socrata({"$select": "max(reporting_month) as m"})[0]["m"]
    latest = pd.Timestamp(latest)
    start = latest - pd.DateOffset(months=months - 1)
    rows = _socrata({
        "$select": ",".join([
            "origin_airport_code as airport",
            "reporting_month as month",
            "total_departures as deps",
            "total_passengers as pax",
            "total_seats as seats",
            "total_distance_flight_sm as avg_dist",
            "domestic_passengers as dom_pax",
            "total_freight_lbs as freight_lbs",
        ]),
        "$where": f"reporting_month >= '{start:%Y-%m-%d}T00:00:00'",
        "$order": "reporting_month, origin_airport_code",
    })
    df = pd.DataFrame(rows)
    for c in ["deps", "pax", "seats", "avg_dist", "dom_pax", "freight_lbs"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["month"] = pd.to_datetime(df["month"])
    # One row per airport-month (a code can map to >1 BTS airport id); distance is weighted.
    df["dist_x_deps"] = df["avg_dist"] * df["deps"]
    df = df.groupby(["airport", "month"], as_index=False)[
        ["deps", "pax", "seats", "dist_x_deps", "dom_pax", "freight_lbs"]].sum()
    return df


def fetch_bts_2019() -> pd.DataFrame:
    """Pre-pandemic baseline: 2019 passengers per origin airport."""
    rows = _socrata({
        "$select": "origin_airport_code as airport, sum(total_passengers) as pax_2019",
        "$where": "year = '2019'",
        "$group": "origin_airport_code",
    })
    df = pd.DataFrame(rows)
    df["pax_2019"] = pd.to_numeric(df["pax_2019"], errors="coerce")
    return df


# ---------------------------------------------------------------- OurAirports
def _csv(url: str) -> pd.DataFrame:
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text), low_memory=False)


def fetch_airports() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (US airports with IATA code + runway count, world airport coordinates by ICAO/ident)."""
    a = _csv(config.OURAIRPORTS_AIRPORTS)
    rw = _csv(config.OURAIRPORTS_RUNWAYS)

    rw = rw[(rw["closed"] == 0) & (rw["length_ft"] >= config.MIN_RUNWAY_LENGTH_FT)]
    runway_count = rw.groupby("airport_ident").size().rename("runways")

    us = a[(a["iso_country"] == "US") & a["iata_code"].notna()].copy()
    us["state"] = us["iso_region"].str.split("-").str[1]
    us = us.rename(columns={"iata_code": "code", "municipality": "city",
                            "latitude_deg": "lat", "longitude_deg": "lon"})
    us["icao"] = us["gps_code"].fillna(us["ident"])
    us = us.merge(runway_count, left_on="ident", right_index=True, how="left")
    # If the same IATA code appears twice, keep the bigger airport type.
    order = {"large_airport": 0, "medium_airport": 1, "small_airport": 2}
    us["_o"] = us["type"].map(order).fillna(9)
    us = us.sort_values("_o").drop_duplicates("code")
    us = us[["code", "icao", "ident", "name", "city", "state", "lat", "lon", "type", "runways"]]

    w = a[a["type"].isin(["large_airport", "medium_airport", "small_airport"])]
    coords = pd.concat([
        w[["ident", "latitude_deg", "longitude_deg"]].rename(columns={"ident": "icao"}),
        w[w["gps_code"].notna()][["gps_code", "latitude_deg", "longitude_deg"]]
        .rename(columns={"gps_code": "icao"}),
    ]).drop_duplicates("icao")
    coords = coords.rename(columns={"latitude_deg": "lat", "longitude_deg": "lon"})
    return us, coords


# ---------------------------------------------------------------- OpenSky
def _opensky_token() -> Optional[str]:
    cid, secret = os.getenv("OPENSKY_CLIENT_ID"), os.getenv("OPENSKY_CLIENT_SECRET")
    if not (cid and secret):
        return None
    r = requests.post(config.OPENSKY_TOKEN_URL, timeout=30, data={
        "grant_type": "client_credentials", "client_id": cid, "client_secret": secret})
    r.raise_for_status()
    return r.json()["access_token"]


def fetch_opensky_departures(icao: str, days: int = config.OPENSKY_DAYS) -> Tuple[List[dict], List[str], List[str]]:
    """Departures from `icao` over the last `days` complete UTC days (ending 2 days ago,
    because OpenSky processes flights overnight). Each day is cached.
    Returns (flights, days_used, notes)."""
    OPENSKY_CACHE.mkdir(parents=True, exist_ok=True)
    notes: List[str] = []
    today = datetime.now(timezone.utc).date()
    wanted = [today - timedelta(days=d) for d in range(2, 2 + days)]

    token = None
    try:
        token = _opensky_token()
    except Exception as e:  # noqa: BLE001
        notes.append(f"OpenSky login failed ({e}); using cached days only.")

    flights: List[dict] = []
    used: List[str] = []
    for day in wanted:
        f = OPENSKY_CACHE / f"{icao}_{day}.json"
        if f.exists():
            flights += json.loads(f.read_text())
            used.append(str(day))
            continue
        if not token:
            continue
        begin = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
        r = requests.get(f"{config.OPENSKY_API}/flights/departure", timeout=60,
                         headers={"Authorization": f"Bearer {token}"},
                         params={"airport": icao, "begin": begin, "end": begin + 86_399})
        if r.status_code == 404:  # OpenSky returns 404 when there are no flights
            day_flights: List[dict] = []
        elif r.ok:
            day_flights = r.json()
        else:
            notes.append(f"OpenSky returned HTTP {r.status_code} for {day}; day skipped.")
            continue
        f.write_text(json.dumps(day_flights))
        flights += day_flights
        used.append(str(day))

    if not used:  # no credentials and no cache for the recent window -> use latest cached days
        cached = sorted(OPENSKY_CACHE.glob(f"{icao}_*.json"))[-days:]
        for f in cached:
            flights += json.loads(f.read_text())
            used.append(f.stem.split("_")[1])
        if cached:
            notes.append("No OpenSky credentials: using the most recent cached days.")
        else:
            notes.append("No OpenSky credentials and no cached data for this airport.")
    elif len(used) < days:
        notes.append(f"Only {len(used)} of {days} requested days were available.")
    return flights, sorted(used), notes


# ---------------------------------------------------------------- cache orchestration
FILES = {
    "monthly": CACHE / "bts_monthly.csv",
    "base2019": CACHE / "bts_2019.csv",
    "airports": CACHE / "airports_us.csv",
    "coords": CACHE / "airport_coords_world.csv",
}


def refresh_cache() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    print("BTS T-100 monthly (last 24 months)...")
    fetch_bts_monthly().to_csv(FILES["monthly"], index=False)
    print("BTS 2019 baseline...")
    fetch_bts_2019().to_csv(FILES["base2019"], index=False)
    print("OurAirports (airports + runways)...")
    us, coords = fetch_airports()
    us.to_csv(FILES["airports"], index=False)
    coords.to_csv(FILES["coords"], index=False)
    print("Done. Cache written to", CACHE)


def load_all() -> Dict[str, pd.DataFrame]:
    """Load cached data (builds the cache on first run)."""
    if not all(f.exists() for f in FILES.values()):
        refresh_cache()
    d = {k: pd.read_csv(f) for k, f in FILES.items()}
    d["monthly"]["month"] = pd.to_datetime(d["monthly"]["month"])
    return d


if __name__ == "__main__":
    if "--refresh" in sys.argv:
        refresh_cache()
    data = load_all()
    m = data["monthly"]
    print(f"\nMonthly rows: {len(m):,} | airports: {m.airport.nunique():,} | "
          f"months: {m.month.min():%Y-%m} .. {m.month.max():%Y-%m}")
    last12 = m[m.month > m.month.max() - pd.DateOffset(months=12)]
    s = last12.groupby("airport")[["pax", "seats", "deps", "dist_x_deps"]].sum()
    s["load_factor"] = (s.pax / s.seats).round(3)
    s["avg_stage_mi"] = (s.dist_x_deps / s.deps).round(0)
    print("\nSanity check - last 12 months:")
    print(s.loc[s.index.intersection(["SFO", "LAX", "SNA", "ANC", "BOS"]),
                ["pax", "seats", "deps", "load_factor", "avg_stage_mi"]])
    print("\nSFO monthly (check the last months are not incomplete):")
    print(m[m.airport == "SFO"][["month", "pax", "dom_pax", "seats"]].tail(8).to_string(index=False))
    if "--opensky" in sys.argv:
        fl, used, notes = fetch_opensky_departures("PANC")
        print(f"\nOpenSky PANC: {len(fl)} departures over days {used} {notes}")
