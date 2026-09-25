"""Deterministic KPIs and scores. No LLM here - every number the agent reports comes from this file."""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List, Optional

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
# percentile column -> underlying KPI column
PCT_SOURCE = {
    "scale": "pax",
    "load_factor": "load_factor",
    "peak_load_factor": "peak_load_factor",
    "pax_growth": "pax_growth",
    "supply_gap": "supply_gap",
    "runway_strain": "movements_per_runway_day",
}


def build_kpis(monthly: pd.DataFrame, base2019: pd.DataFrame, airports: pd.DataFrame) -> pd.DataFrame:
    """One row per US primary airport with KPIs, national percentiles, Expansion Score, Congestion Index."""
    m = monthly
    latest = m["month"].max()
    l12_start = latest - pd.DateOffset(months=11)
    p12_start, p12_end = latest - pd.DateOffset(months=23), latest - pd.DateOffset(months=12)
    cur = m[(m["month"] >= l12_start) & (m["month"] <= latest)]
    prev = m[(m["month"] >= p12_start) & (m["month"] <= p12_end)]

    k = cur.groupby("airport")[["pax", "seats", "deps", "dist_x_deps", "dom_pax", "freight_lbs"]].sum()
    k = k.join(prev.groupby("airport")[["pax", "seats"]].sum().add_suffix("_prev"))

    monthly_lf = cur[cur["seats"] > 0].assign(lf=lambda d: d["pax"] / d["seats"])
    idx = monthly_lf.groupby("airport")["lf"].idxmax()
    peak = monthly_lf.loc[idx].set_index("airport")
    k["peak_load_factor"] = peak["lf"]
    k["peak_month"] = peak["month"].dt.strftime("%b %Y")

    k = k.join(base2019.set_index("airport")["pax_2019"])
    k = k.join(airports.set_index("code")[["name", "city", "state", "icao", "lat", "lon", "runways"]], how="inner")

    k["load_factor"] = k["pax"] / k["seats"]
    k["pax_growth"] = k["pax"] / k["pax_prev"] - 1
    k["seat_growth"] = k["seats"] / k["seats_prev"] - 1
    k["supply_gap"] = k["pax_growth"] - k["seat_growth"]
    k["movements_per_runway_day"] = 2 * k["deps"] / 365 / k["runways"]  # departures x2 = arr+dep
    k["avg_stage_miles"] = k["dist_x_deps"] / k["deps"]
    k["pax_vs_2019"] = k["pax"] / k["pax_2019"] - 1
    k["intl_share"] = 1 - k["dom_pax"] / k["pax"]
    k["seats_per_dep"] = k["seats"] / k["deps"]

    k = k[(k["pax"] >= config.MIN_ENPLANEMENTS) & (k["seats"] > 0)].copy()
    k = k.replace([math.inf, -math.inf], float("nan"))

    for p, src in PCT_SOURCE.items():
        k[f"pct_{p}"] = (k[src].rank(pct=True) * 100).fillna(50.0)  # missing -> neutral 50

    k["expansion_score"] = sum(w * k[f"pct_{p}"] for p, w in config.EXPANSION_WEIGHTS.items())
    k["congestion_index"] = sum(k[f"pct_{p}"] for p in config.CONGESTION_COMPONENTS) / len(config.CONGESTION_COMPONENTS)
    k["expansion_rank_national"] = k["expansion_score"].rank(ascending=False, method="min").astype(int)
    k["unmet_daily_departures"] = k.apply(lambda r: unmet_capacity(r)["extra_daily_departures"], axis=1)

    k.attrs["window"] = f"{l12_start:%b %Y}-{latest:%b %Y}"
    k.attrs["prev_window"] = f"{p12_start:%b %Y}-{p12_end:%b %Y}"
    k.attrs["universe_size"] = len(k)
    return k


def drivers(row: pd.Series) -> Dict[str, List[str]]:
    """Which KPIs push the Expansion Score up (>=70th pct) or down (<=30th pct)."""
    strong = [LABELS[p] for p in config.EXPANSION_WEIGHTS if row[f"pct_{p}"] >= 70]
    weak = [LABELS[p] for p in config.EXPANSION_WEIGHTS if row[f"pct_{p}"] <= 30]
    return {"strengths": strong, "weaknesses": weak}


def unmet_capacity(row: pd.Series, target_lf: float = config.TARGET_LOAD_FACTOR) -> Dict[str, float]:
    """Seats/flights missing to bring the load factor down to `target_lf`."""
    extra_seats = max(0.0, row["pax"] / target_lf - row["seats"])
    spd = row["seats_per_dep"] if row["seats_per_dep"] and row["seats_per_dep"] > 0 else float("nan")
    extra_deps_day = extra_seats / spd / 365 if spd == spd else float("nan")
    return {"extra_annual_seats": round(extra_seats), "extra_daily_departures": round(extra_deps_day, 1)}


def unmet_signals(row: pd.Series) -> List[str]:
    """Deterministic, human-readable reasons behind (or against) unmet demand."""
    s = []
    hi = config.HIGH_PERCENTILE
    lf, p = row["load_factor"], row["pct_load_factor"]
    if p >= hi:
        s.append(f"Flights are {lf:.1%} full on average, fuller than {p:.0f}% of US airports: little spare seat capacity.")
    else:
        s.append(f"Average load factor {lf:.1%} (fuller than {p:.0f}% of US airports): some spare seats remain.")
    if row["pct_peak_load_factor"] >= hi:
        s.append(f"Peak month ({row['peak_month']}) reached {row['peak_load_factor']:.1%} "
                 f"(top {100 - hi}% nationally): seasonal capacity crunch.")
    g, sg = row["pax_growth"], row["seat_growth"]
    if g == g and sg == sg:
        verb = "outpacing" if g > sg else "not outpacing"
        s.append(f"Passengers {g:+.1%} vs seats {sg:+.1%} year-over-year: demand {verb} supply.")
    if row["pct_runway_strain"] >= config.HIGH_PERCENTILE:
        s.append(f"~{row['movements_per_runway_day']:.0f} movements per runway per day "
                 f"(top {100 - config.HIGH_PERCENTILE}% nationally): the airfield limits adding flights.")
    v = row["pax_vs_2019"]
    if v == v:
        if v < -0.01 and p >= hi:
            s.append(f"Passengers are still {-v:.1%} below 2019 while flights are this full: "
                     f"seats offered, not travel demand, look like the constraint.")
        elif v < -0.01:
            s.append(f"Passengers are still {-v:.1%} below 2019: demand has not fully recovered.")
        else:
            s.append(f"Passengers are {v:+.1%} vs 2019 (recovered).")
    return s


# ---------------------------------------------------------------- route distance (OpenSky)
_AIRLINE_CALLSIGN = re.compile(r"^[A-Z]{3}\d")


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 3958.8 * math.asin(math.sqrt(a))


def route_mix(flights: List[dict], origin_icao: str, coords: Dict[str, tuple],
              long_haul_miles: float = config.LONG_HAUL_MILES) -> Dict:
    """Share of departures by great-circle distance band. Only airline-style callsigns are counted."""
    o = coords.get(origin_icao)
    counts = Counter()
    rows = []
    for f in flights:
        cs = (f.get("callsign") or "").strip()
        dest = f.get("estArrivalAirport")
        if not _AIRLINE_CALLSIGN.match(cs):
            counts["excluded_non_airline_callsign"] += 1
            continue
        if not dest or dest == origin_icao or dest not in coords or o is None:
            counts["excluded_unknown_destination"] += 1
            continue
        d = haversine_miles(o[0], o[1], *coords[dest])
        rows.append({"dest": dest, "miles": d, "cargo": cs[:3] in config.CARGO_CALLSIGN_PREFIXES})

    n = len(rows)
    if n == 0:
        return {"flights_analyzed": 0, **counts}
    df = pd.DataFrame(rows)
    pax_like = df[~df["cargo"]]
    top = df.groupby("dest")["miles"].agg(["count", "mean"]).sort_values("count", ascending=False).head(8)
    return {
        "flights_total_raw": len(flights),
        "flights_analyzed": n,
        **counts,
        "destination_coverage_pct": round(100 * n / (n + counts["excluded_unknown_destination"]), 1),
        "long_haul_threshold_miles": long_haul_miles,
        "long_haul_share_pct": round(100 * (df["miles"] >= long_haul_miles).mean(), 1),
        "long_haul_share_excl_known_cargo_pct": (
            round(100 * (pax_like["miles"] >= long_haul_miles).mean(), 1) if len(pax_like) else None),
        "known_cargo_operator_share_pct": round(100 * df["cargo"].mean(), 1),
        "bands_pct": {
            f"short (<{config.SHORT_HAUL_MILES} mi)": round(100 * (df["miles"] < config.SHORT_HAUL_MILES).mean(), 1),
            f"medium ({config.SHORT_HAUL_MILES}-{long_haul_miles:.0f} mi)": round(
                100 * ((df["miles"] >= config.SHORT_HAUL_MILES) & (df["miles"] < long_haul_miles)).mean(), 1),
            f"long (>={long_haul_miles:.0f} mi)": round(100 * (df["miles"] >= long_haul_miles).mean(), 1),
        },
        "top_destinations": [
            {"icao": i, "flights": int(r["count"]), "miles": round(r["mean"])} for i, r in top.iterrows()],
    }


def filter_states(k: pd.DataFrame, states: Optional[List[str]]) -> pd.DataFrame:
    if not states:
        return k
    return k[k["state"].isin([s.upper() for s in states])]
