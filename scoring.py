"""Deterministic KPIs and scores. No LLM here: every number the agent reports is computed in this file."""
from __future__ import annotations

import math
import re

import pandas as pd

import config

LABELS = {
    "scale": "passenger volume",
    "load_factor": "load factor (how full flights are)",
    "peak_load_factor": "peak-month load factor",
    "pax_growth": "passenger growth",
    "supply_gap": "demand outpacing seat supply",
    "runway_strain": "movements per runway",
}

# Score component -> the KPI column it is ranked on
COMPONENT_KPI = {
    "scale": "pax",
    "load_factor": "load_factor",
    "peak_load_factor": "peak_load_factor",
    "pax_growth": "pax_growth",
    "supply_gap": "supply_gap",
    "runway_strain": "movements_per_runway_day",
}


def build_kpis(monthly: pd.DataFrame, base2019: pd.DataFrame, airports: pd.DataFrame) -> pd.DataFrame:
    """One row per US commercial airport with KPIs, national percentiles and scores."""
    # 1. Time windows: last 12 months vs the 12 months before
    latest = monthly["month"].max()
    last12_start = latest - pd.DateOffset(months=11)
    prev12_start = latest - pd.DateOffset(months=23)
    prev12_end = latest - pd.DateOffset(months=12)
    last12 = monthly[monthly["month"].between(last12_start, latest)]
    prev12 = monthly[monthly["month"].between(prev12_start, prev12_end)]

    # 2. Totals per airport
    k = last12.groupby("airport")[["pax", "seats", "deps", "dist_x_deps", "dom_pax"]].sum()
    prev = prev12.groupby("airport")[["pax", "seats"]].sum()
    k["pax_prev"] = prev["pax"]
    k["seats_prev"] = prev["seats"]

    # 3. Peak month = the month with the highest load factor
    months = last12[last12["seats"] > 0].copy()
    months["lf"] = months["pax"] / months["seats"]
    peak = months.loc[months.groupby("airport")["lf"].idxmax()].set_index("airport")
    k["peak_load_factor"] = peak["lf"]
    k["peak_month"] = peak["month"].dt.strftime("%b %Y")

    # 4. Add the 2019 baseline and airport info (name, state, runways)
    k = k.join(base2019.set_index("airport")["pax_2019"])
    info = airports.set_index("code")[["name", "city", "state", "icao", "lat", "lon", "runways"]]
    k = k.join(info, how="inner")

    # 5. KPIs
    k["load_factor"] = k["pax"] / k["seats"]
    k["pax_growth"] = k["pax"] / k["pax_prev"] - 1
    k["seat_growth"] = k["seats"] / k["seats_prev"] - 1
    k["supply_gap"] = k["pax_growth"] - k["seat_growth"]
    k["movements_per_runway_day"] = 2 * k["deps"] / 365 / k["runways"]  # each departure also has an arrival
    k["avg_stage_miles"] = k["dist_x_deps"] / k["deps"]
    k["pax_vs_2019"] = k["pax"] / k["pax_2019"] - 1
    k["intl_share"] = 1 - k["dom_pax"] / k["pax"]
    k["seats_per_dep"] = k["seats"] / k["deps"]

    # 6. Compare only commercial airports (FAA "primary": over 10,000 enplanements a year)
    k = k[(k["pax"] >= config.MIN_ENPLANEMENTS) & (k["seats"] > 0)].copy()
    k = k.replace([math.inf, -math.inf], float("nan"))

    # 7. National percentile (0-100) per component; missing data counts as neutral (50)
    for component, kpi in COMPONENT_KPI.items():
        k[f"pct_{component}"] = (k[kpi].rank(pct=True) * 100).fillna(50.0)

    # 8. Scores
    k["expansion_score"] = sum(weight * k[f"pct_{c}"] for c, weight in config.EXPANSION_WEIGHTS.items())
    k["congestion_index"] = k[[f"pct_{c}" for c in config.CONGESTION_COMPONENTS]].mean(axis=1)
    k["expansion_rank"] = k["expansion_score"].rank(ascending=False, method="min").astype(int)
    k["unmet_daily_departures"] = [unmet_capacity(row)["extra_daily_departures"] for _, row in k.iterrows()]

    k.attrs["window"] = f"{last12_start:%b %Y}-{latest:%b %Y}"
    k.attrs["prev_window"] = f"{prev12_start:%b %Y}-{prev12_end:%b %Y}"
    k.attrs["universe_size"] = len(k)
    return k


def drivers(row: pd.Series) -> dict[str, list[str]]:
    """Score components in the national top 30% (strengths) or bottom 30% (weaknesses)."""
    strengths = [LABELS[c] for c in config.EXPANSION_WEIGHTS if row[f"pct_{c}"] >= 70]
    weaknesses = [LABELS[c] for c in config.EXPANSION_WEIGHTS if row[f"pct_{c}"] <= 30]
    return {"strengths": strengths, "weaknesses": weaknesses}


def unmet_capacity(row: pd.Series, target_lf: float = config.TARGET_LOAD_FACTOR) -> dict:
    """Seats (and daily flights) missing so that flights are only `target_lf` full."""
    extra_seats = max(0.0, row["pax"] / target_lf - row["seats"])
    extra_daily_departures = extra_seats / row["seats_per_dep"] / 365
    return {"extra_annual_seats": round(extra_seats),
            "extra_daily_departures": round(float(extra_daily_departures), 1)}


def unmet_signals(row: pd.Series) -> list[str]:
    """Plain-language reasons behind (or against) unmet demand. Thresholds are national percentiles."""
    signals = []
    high = config.HIGH_PERCENTILE
    lf, lf_pct = row["load_factor"], row["pct_load_factor"]

    if lf_pct >= high:
        signals.append(f"Flights are {lf:.1%} full on average, fuller than {lf_pct:.0f}% of US airports: "
                       f"little spare seat capacity.")
    else:
        signals.append(f"Average load factor {lf:.1%} (fuller than {lf_pct:.0f}% of US airports): "
                       f"some spare seats remain.")

    if row["pct_peak_load_factor"] >= high:
        signals.append(f"Peak month ({row['peak_month']}) reached {row['peak_load_factor']:.1%} "
                       f"(top {100 - high}% nationally): seasonal capacity crunch.")

    growth, seat_growth = row["pax_growth"], row["seat_growth"]
    if pd.notna(growth) and pd.notna(seat_growth):
        verb = "outpacing" if growth > seat_growth else "not outpacing"
        signals.append(f"Passengers {growth:+.1%} vs seats {seat_growth:+.1%} year-over-year: "
                       f"demand {verb} supply.")

    if row["pct_runway_strain"] >= high:
        signals.append(f"~{row['movements_per_runway_day']:.0f} movements per runway per day "
                       f"(top {100 - high}% nationally): the airfield limits adding flights.")

    vs_2019 = row["pax_vs_2019"]
    if pd.notna(vs_2019):
        if vs_2019 < -0.01 and lf_pct >= high:
            signals.append(f"Passengers are still {-vs_2019:.1%} below 2019 while flights are this full: "
                           f"seats offered, not travel demand, look like the constraint.")
        elif vs_2019 < -0.01:
            signals.append(f"Passengers are still {-vs_2019:.1%} below 2019: demand has not fully recovered.")
        else:
            signals.append(f"Passengers are {vs_2019:+.1%} vs 2019 (recovered).")
    return signals


# ---------- Route distance (OpenSky flights) ----------

AIRLINE_CALLSIGN = re.compile(r"^[A-Z]{3}\d")  # e.g. ASA123; private planes look like N123AB


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in statute miles."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_lat, d_lon = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lon / 2) ** 2
    return 2 * 3958.8 * math.asin(math.sqrt(a))


def route_mix(flights: list[dict], origin_icao: str, coords: dict[str, tuple],
              long_haul_miles: float = config.LONG_HAUL_MILES) -> dict:
    """Share of airline departures by distance band."""
    origin = coords.get(origin_icao)
    non_airline, unknown_destination = 0, 0
    rows = []
    for flight in flights:
        callsign = (flight.get("callsign") or "").strip()
        destination = flight.get("estArrivalAirport")
        if not AIRLINE_CALLSIGN.match(callsign):
            non_airline += 1
        elif origin is None or not destination or destination == origin_icao or destination not in coords:
            unknown_destination += 1
        else:
            miles = haversine_miles(origin[0], origin[1], *coords[destination])
            rows.append({"dest": destination, "miles": miles,
                         "cargo": callsign[:3] in config.CARGO_CALLSIGN_PREFIXES})

    counts = {"excluded_non_airline_callsign": non_airline, "excluded_unknown_destination": unknown_destination}
    if not rows:
        return {"flights_analyzed": 0, **counts}

    df = pd.DataFrame(rows)
    passenger_like = df[~df["cargo"]]
    short = df["miles"] < config.SHORT_HAUL_MILES
    long = df["miles"] >= long_haul_miles
    medium = ~short & ~long

    def share(mask) -> float:
        return round(100 * float(mask.mean()), 1)

    top = df.groupby("dest")["miles"].agg(["count", "mean"]).sort_values("count", ascending=False).head(8)
    return {
        "flights_total_raw": len(flights),
        "flights_analyzed": len(df),
        **counts,
        "destination_coverage_pct": round(100 * len(df) / (len(df) + unknown_destination), 1),
        "long_haul_threshold_miles": long_haul_miles,
        "long_haul_share_pct": share(long),
        "long_haul_share_excl_known_cargo_pct": (
            share(passenger_like["miles"] >= long_haul_miles) if len(passenger_like) else None),
        "known_cargo_operator_share_pct": share(df["cargo"]),
        "bands_pct": {
            f"short (<{config.SHORT_HAUL_MILES} mi)": share(short),
            f"medium ({config.SHORT_HAUL_MILES}-{long_haul_miles:.0f} mi)": share(medium),
            f"long (>={long_haul_miles:.0f} mi)": share(long),
        },
        "top_destinations": [{"icao": icao, "flights": int(r["count"]), "miles": round(r["mean"])}
                             for icao, r in top.iterrows()],
    }
