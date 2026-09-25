"""The functions the LLM is allowed to call. Each returns a compact JSON-able dict
with the numbers, the data window and the assumptions behind them."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Dict, List, Optional

import pandas as pd

import config
import data_sources
import scoring


@lru_cache(maxsize=1)
def _data():
    d = data_sources.load_all()
    k = scoring.build_kpis(d["monthly"], d["base2019"], d["airports"])
    coords = {r.icao: (r.lat, r.lon) for r in d["coords"].itertuples()}
    return d, k, coords


def _context(k: pd.DataFrame) -> Dict:
    return {
        "data_window": f"{k.attrs['window']} (vs prior 12 months {k.attrs['prev_window']})",
        "source": "BTS T-100 segment data by origin airport (enplaned passengers, seats, departures); "
                  "runways from OurAirports",
        "universe": f"{k.attrs['universe_size']} US airports with >= {config.MIN_ENPLANEMENTS:,} enplanements",
    }


def _pct(x) -> Optional[float]:
    return None if x != x else round(100 * float(x), 1)


def _airport_row(code: str, r: pd.Series) -> Dict:
    return {
        "code": code, "name": r["name"], "city": r["city"], "state": r["state"],
        "expansion_score": round(r["expansion_score"], 1),
        "national_rank": f"{r['expansion_rank_national']} of {len(_data()[1])}",
        "congestion_index": round(r["congestion_index"], 1),
        "enplaned_passengers_12m": int(r["pax"]),
        "passenger_growth_pct": _pct(r["pax_growth"]),
        "seat_growth_pct": _pct(r["seat_growth"]),
        "load_factor_pct": _pct(r["load_factor"]),
        "peak_month_load_factor_pct": _pct(r["peak_load_factor"]),
        "peak_month": r["peak_month"],
        "movements_per_runway_per_day": None if r["movements_per_runway_day"] != r["movements_per_runway_day"]
        else round(r["movements_per_runway_day"], 1),
        "runways": None if r["runways"] != r["runways"] else int(r["runways"]),
        "vs_2019_pct": _pct(r["pax_vs_2019"]),
        "international_share_pct": _pct(r["intl_share"]),
        "avg_flight_distance_miles": round(r["avg_stage_miles"]),
        **scoring.drivers(r),
    }


def _get(code: str):
    d, k, _ = _data()
    code = code.strip().upper()
    if len(code) == 4 and code.startswith(("K", "P")):  # accept ICAO like KSFO / PANC
        hit = k[k["icao"] == code]
        if len(hit):
            return hit.index[0], hit.iloc[0]
    if code in k.index:
        return code, k.loc[code]
    return code, None


# ------------------------------------------------------------------ tools
CITY_ALIASES = {"la": "los angeles", "nyc": "new york", "sf": "san francisco", "dc": "washington",
                "vegas": "las vegas", "philly": "philadelphia"}


def find_airports(query: str) -> Dict:
    d, k, _ = _data()
    q = query.strip().lower()
    q = CITY_ALIASES.get(q, q)
    a = d["airports"]
    city, name = a["city"].fillna("").str.lower(), a["name"].fillna("").str.lower()
    hit = a[a["code"].str.lower().eq(q) | city.str.startswith(q) | (len(q) >= 4) & name.str.contains(q)]
    hit = hit.merge(k[["pax"]], left_on="code", right_index=True, how="inner")
    hit = hit.sort_values("pax", ascending=False).head(8)
    return {"query": query, "matches": [
        {"code": r.code, "name": r.name, "city": r.city, "state": r.state, "enplaned_passengers_12m": int(r.pax)}
        for r in hit.itertuples()],
        "note": "Only commercial airports with BTS traffic are listed, largest first."}


def rank_airports(region: Optional[str] = None, states: Optional[List[str]] = None, top_n: int = 10,
                  sort_by: str = "expansion_score", min_passengers: int = 0) -> Dict:
    _, k, _ = _data()
    if region:
        match = [r for r in config.REGIONS if r.lower() == region.lower()]
        if not match:
            return {"error": f"Unknown region '{region}'. Known: {list(config.REGIONS)}. Or pass `states`."}
        states = config.REGIONS[match[0]]
    sub = scoring.filter_states(k, states)
    sub = sub[sub["pax"] >= min_passengers]
    if sort_by not in {"expansion_score", "congestion_index", "pax_growth", "load_factor", "unmet_daily_departures"}:
        sort_by = "expansion_score"
    sub = sub.sort_values(sort_by, ascending=False).head(max(1, min(int(top_n), 25)))
    return {
        **_context(k),
        "filter": {"region": region, "states": states, "min_passengers": min_passengers},
        "sorted_by": sort_by,
        "method": "Expansion Score 0-100 = weighted national percentiles: "
                  + ", ".join(f"{scoring.LABELS[p]} {int(w * 100)}%" for p, w in config.EXPANSION_WEIGHTS.items()),
        "results": [{"rank": i + 1, **_airport_row(c, r)} for i, (c, r) in enumerate(sub.iterrows())],
    }


def compare_airports(codes: List[str]) -> Dict:
    _, k, _ = _data()
    rows, missing = [], []
    for c in codes[:6]:
        code, r = _get(c)
        (missing.append(code) if r is None else rows.append(_airport_row(code, r)))
    out = {**_context(k), "airports": rows,
           "congestion_index_method": "average of national percentiles of load factor, peak-month load factor "
                                      "and movements per runway (0-100, higher = more congested)"}
    if missing:
        out["not_found"] = missing
    if len(rows) >= 2:
        out["most_congested"] = max(rows, key=lambda x: x["congestion_index"])["code"]
        out["highest_expansion_score"] = max(rows, key=lambda x: x["expansion_score"])["code"]
    return out


def analyze_unmet_demand(code: str, target_load_factor: float = config.TARGET_LOAD_FACTOR) -> Dict:
    _, k, _ = _data()
    code, r = _get(code)
    if r is None:
        return {"error": f"{code} not found among US commercial airports in BTS data."}
    u = scoring.unmet_capacity(r, target_load_factor)
    return {
        **_context(k),
        "airport": _airport_row(code, r),
        "unmet_demand_estimate": {
            "passengers_12m": int(r["pax"]),
            "seats_offered_12m": int(r["seats"]),
            "seats_needed_at_target_lf": int(round(r["pax"] / target_load_factor)),
            "avg_seats_per_departure": round(float(r["seats_per_dep"])),
            **u,
            "method": f"Seats needed so that 12-month load factor falls to {target_load_factor:.0%}: "
                      f"passengers / {target_load_factor:.2f} - seats offered; flights = seats / avg seats per "
                      f"departure ({r['seats_per_dep']:.0f}) / 365.",
        },
        "signals": scoring.unmet_signals(r),
        "caveats": [
            "Proxy, not observed demand: BTS counts flown passengers, so people who could not get a seat "
            "or chose another airport are not visible.",
            "Seats per departure includes all-cargo departures, which can overstate the flight estimate at cargo-heavy airports.",
            "Movements per runway count only BTS-reporting commercial carriers (no general aviation / military).",
        ],
    }


def route_distance_mix(code: str, long_haul_miles: float = config.LONG_HAUL_MILES,
                       days: int = config.OPENSKY_DAYS) -> Dict:
    d, k, coords = _data()
    code, r = _get(code)
    if r is None:
        return {"error": f"{code} not found."}
    flights, used, notes = data_sources.fetch_opensky_departures(r["icao"], int(min(days, 7)))
    mix = scoring.route_mix(flights, r["icao"], coords, long_haul_miles)
    if mix["flights_analyzed"] == 0:
        return {
            "airport": code, "status": "NO_DATA",
            "instruction": "The long-haul share CANNOT be computed: no observed flights available. "
                           "Do NOT report 0%. Tell the user the data is missing and why.",
            "notes": notes,
            "bts_avg_flight_distance_miles_12m": round(r["avg_stage_miles"]),
            "bts_note": "Average distance is a mean across all flights (incl. cargo); it cannot give a share.",
        }
    return {
        "airport": code, "icao": r["icao"],
        "source": "OpenSky Network ADS-B departures (sample of observed flights), great-circle distance",
        "days_used": used, "notes": notes, **mix,
        "bts_avg_flight_distance_miles_12m": round(r["avg_stage_miles"]),
        "caveats": [
            "OpenSky is crowd-sourced coverage: flights with no detected destination are excluded.",
            "Includes cargo flights; see the 'excluding known cargo operators' figure.",
            f"Long-haul threshold is an assumption ({long_haul_miles:.0f} mi); ask to change it.",
        ],
    }


def monthly_trend(code: str) -> Dict:
    d, k, _ = _data()
    code, r = _get(code)
    if r is None:
        return {"error": f"{code} not found."}
    m = d["monthly"][d["monthly"]["airport"] == code].sort_values("month")
    return {"airport": code, "months": [
        {"month": f"{x.month:%Y-%m}", "passengers": int(x.pax), "seats": int(x.seats),
         "load_factor_pct": round(100 * x.pax / x.seats, 1) if x.seats else None} for x in m.itertuples()]}


FUNCTIONS = {f.__name__: f for f in
             [find_airports, rank_airports, compare_airports, analyze_unmet_demand, route_distance_mix, monthly_trend]}

_code = {"type": "string", "description": "IATA code, e.g. SFO (ICAO like KSFO also accepted)"}
SCHEMAS = [
    {"type": "function", "function": {
        "name": "find_airports",
        "description": "Look up US commercial airports by city, name or code. Use when the user names a city "
                       "or airport without a clear IATA code (e.g. 'LA', 'Santa Ana').",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "rank_airports",
        "description": "Rank US airports in a region or list of states by Expansion Score (investment "
                       "attractiveness) or another KPI. Use for 'which airports are strong candidates...'.",
        "parameters": {"type": "object", "properties": {
            "region": {"type": "string", "enum": list(config.REGIONS)},
            "states": {"type": "array", "items": {"type": "string"}, "description": "2-letter state codes"},
            "top_n": {"type": "integer", "default": 10},
            "sort_by": {"type": "string", "enum": ["expansion_score", "congestion_index", "pax_growth",
                                                   "load_factor", "unmet_daily_departures"]},
            "min_passengers": {"type": "integer", "description": "min 12-month enplanements, default 0"}}}}},
    {"type": "function", "function": {
        "name": "compare_airports",
        "description": "Side-by-side KPIs, Congestion Index and Expansion Score for 2-6 airports.",
        "parameters": {"type": "object", "properties": {
            "codes": {"type": "array", "items": {"type": "string"}}}, "required": ["codes"]}}},
    {"type": "function", "function": {
        "name": "analyze_unmet_demand",
        "description": "Estimate unmet flight demand (missing seats/daily flights) for one airport and the "
                       "data signals explaining why.",
        "parameters": {"type": "object", "properties": {
            "code": _code, "target_load_factor": {"type": "number", "default": 0.8}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "route_distance_mix",
        "description": "Share of short/medium/long-haul departures from an airport, from observed flights "
                       "(OpenSky). Use for long-haul percentage questions.",
        "parameters": {"type": "object", "properties": {
            "code": _code, "long_haul_miles": {"type": "number", "default": config.LONG_HAUL_MILES},
            "days": {"type": "integer", "default": config.OPENSKY_DAYS}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "monthly_trend",
        "description": "Monthly passengers, seats and load factor for the last 24 months for one airport.",
        "parameters": {"type": "object", "properties": {"code": _code}, "required": ["code"]}}},
]


def run_tool(name: str, args: Dict) -> Dict:
    if name not in FUNCTIONS:
        return {"error": f"unknown tool {name}"}
    try:
        return FUNCTIONS[name](**(args or {}))
    except Exception as e:  # noqa: BLE001 - surface the problem to the LLM instead of crashing
        return {"error": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":  # quick manual check without any LLM
    print(json.dumps(rank_airports(region="New England", top_n=5), indent=2))
    print(json.dumps(compare_airports(["LAX", "SNA"]), indent=2))
    print(json.dumps(analyze_unmet_demand("SFO"), indent=2))
