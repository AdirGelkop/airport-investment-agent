"""The functions the LLM can call. Each returns a small JSON-ready dict with the numbers,
the data window and the assumptions behind them."""
from __future__ import annotations

import json
from functools import lru_cache

import pandas as pd

import config
import data_sources
import scoring

CITY_ALIASES = {"la": "los angeles", "nyc": "new york", "sf": "san francisco", "dc": "washington",
                "vegas": "las vegas", "philly": "philadelphia"}


@lru_cache(maxsize=1)
def load_data():
    """Load the cache once and compute all KPIs. Returns (raw data, KPI table, coordinates by ICAO)."""
    data = data_sources.load_all()
    kpis = scoring.build_kpis(data["monthly"], data["base2019"], data["airports"])
    coords = {row.icao: (row.lat, row.lon) for row in data["coords"].itertuples()}
    return data, kpis, coords


# ---------- helpers ----------

def find_airport_row(code: str):
    """Look up an airport by IATA (SFO) or ICAO (KSFO). Returns (code, KPI row or None)."""
    _, kpis, _ = load_data()
    code = code.strip().upper()
    if code in kpis.index:
        return code, kpis.loc[code]
    by_icao = kpis[kpis["icao"] == code]
    if len(by_icao):
        return by_icao.index[0], by_icao.iloc[0]
    return code, None


def percent(x):
    return None if pd.isna(x) else round(100 * float(x), 1)


def number(x, digits=1):
    return None if pd.isna(x) else round(float(x), digits)


def data_context() -> dict:
    _, kpis, _ = load_data()
    return {
        "data_window": f"{kpis.attrs['window']} (vs prior 12 months {kpis.attrs['prev_window']})",
        "source": "BTS T-100 segment data by origin airport (enplaned passengers, seats, departures); "
                  "runways from OurAirports",
        "universe": f"{kpis.attrs['universe_size']} US airports with >= {config.MIN_ENPLANEMENTS:,} enplanements",
    }


def airport_summary(code: str, row: pd.Series) -> dict:
    """The KPIs of one airport, rounded for the LLM."""
    _, kpis, _ = load_data()
    return {
        "code": code, "name": row["name"], "city": row["city"], "state": row["state"],
        "expansion_score": number(row["expansion_score"]),
        "national_rank": f"{row['expansion_rank']} of {len(kpis)}",
        "congestion_index": number(row["congestion_index"]),
        "enplaned_passengers_12m": int(row["pax"]),
        "passenger_growth_pct": percent(row["pax_growth"]),
        "seat_growth_pct": percent(row["seat_growth"]),
        "load_factor_pct": percent(row["load_factor"]),
        "peak_month_load_factor_pct": percent(row["peak_load_factor"]),
        "peak_month": row["peak_month"],
        "movements_per_runway_per_day": number(row["movements_per_runway_day"]),
        "runways": None if pd.isna(row["runways"]) else int(row["runways"]),
        "vs_2019_pct": percent(row["pax_vs_2019"]),
        "international_share_pct": percent(row["intl_share"]),
        "avg_flight_distance_miles": number(row["avg_stage_miles"], 0),
        **scoring.drivers(row),
    }


# ---------- tools ----------

def find_airports(query: str) -> dict:
    data, kpis, _ = load_data()
    q = query.strip().lower()
    q = CITY_ALIASES.get(q, q)
    airports = data["airports"]
    city = airports["city"].fillna("").str.lower()
    name = airports["name"].fillna("").str.lower()
    match = airports["code"].str.lower().eq(q) | city.str.startswith(q)
    if len(q) >= 4:
        match = match | name.str.contains(q)

    hits = airports[match].merge(kpis[["pax"]], left_on="code", right_index=True)  # only airports with traffic
    hits = hits.sort_values("pax", ascending=False).head(8)
    return {
        "query": query,
        "matches": [{"code": r.code, "name": r.name, "city": r.city, "state": r.state,
                     "enplaned_passengers_12m": int(r.pax)} for r in hits.itertuples()],
        "note": "Only commercial airports with BTS traffic are listed, largest first.",
    }


def rank_airports(region: str | None = None, states: list[str] | None = None, top_n: int = 10,
                  sort_by: str = "expansion_score", min_passengers: int = 0) -> dict:
    _, kpis, _ = load_data()
    if region:
        known = {r.lower(): r for r in config.REGIONS}
        if region.lower() not in known:
            return {"error": f"Unknown region '{region}'. Known: {list(config.REGIONS)}. Or pass `states`."}
        states = config.REGIONS[known[region.lower()]]

    selected = kpis
    if states:
        selected = selected[selected["state"].isin([s.upper() for s in states])]
    selected = selected[selected["pax"] >= min_passengers]

    allowed = {"expansion_score", "congestion_index", "pax_growth", "load_factor", "unmet_daily_departures"}
    if sort_by not in allowed:
        sort_by = "expansion_score"
    top_n = max(1, min(int(top_n), 25))
    selected = selected.sort_values(sort_by, ascending=False).head(top_n)

    weights = ", ".join(f"{scoring.LABELS[c]} {int(w * 100)}%" for c, w in config.EXPANSION_WEIGHTS.items())
    return {
        **data_context(),
        "filter": {"region": region, "states": states, "min_passengers": min_passengers},
        "sorted_by": sort_by,
        "method": "Expansion Score 0-100 = weighted national percentiles: " + weights,
        "results": [{"rank": i + 1, **airport_summary(code, row)}
                    for i, (code, row) in enumerate(selected.iterrows())],
    }


def compare_airports(codes: list[str]) -> dict:
    found, missing = [], []
    for c in codes[:6]:
        code, row = find_airport_row(c)
        if row is None:
            missing.append(code)
        else:
            found.append(airport_summary(code, row))

    result = {
        **data_context(),
        "airports": found,
        "congestion_index_method": "average of national percentiles of load factor, peak-month load factor "
                                   "and movements per runway (0-100, higher = more congested)",
    }
    if missing:
        result["not_found"] = missing
    if len(found) >= 2:
        result["most_congested"] = max(found, key=lambda a: a["congestion_index"])["code"]
        result["highest_expansion_score"] = max(found, key=lambda a: a["expansion_score"])["code"]
    return result


def analyze_unmet_demand(code: str, target_load_factor: float = config.TARGET_LOAD_FACTOR) -> dict:
    code, row = find_airport_row(code)
    if row is None:
        return {"error": f"{code} not found among US commercial airports in BTS data."}
    unmet = scoring.unmet_capacity(row, target_load_factor)
    seats_per_dep = round(float(row["seats_per_dep"]))
    return {
        **data_context(),
        "airport": airport_summary(code, row),
        "unmet_demand_estimate": {
            "passengers_12m": int(row["pax"]),
            "seats_offered_12m": int(row["seats"]),
            "seats_needed_at_target_lf": round(row["pax"] / target_load_factor),
            "avg_seats_per_departure": seats_per_dep,
            **unmet,
            "method": f"Seats needed so that 12-month load factor falls to {target_load_factor:.0%}: "
                      f"passengers / {target_load_factor:.2f} - seats offered; flights = seats / avg seats per "
                      f"departure ({seats_per_dep}) / 365.",
        },
        "signals": scoring.unmet_signals(row),
        "caveats": [
            "Proxy, not observed demand: BTS counts flown passengers, so people who could not get a seat "
            "or chose another airport are not visible.",
            "Seats per departure includes all-cargo departures, which can overstate the flight estimate "
            "at cargo-heavy airports.",
            "Movements per runway count only BTS-reporting commercial carriers (no general aviation / military).",
        ],
    }


def route_distance_mix(code: str, long_haul_miles: float = config.LONG_HAUL_MILES,
                       days: int = config.OPENSKY_DAYS) -> dict:
    _, _, coords = load_data()
    code, row = find_airport_row(code)
    if row is None:
        return {"error": f"{code} not found."}

    flights, days_used, notes = data_sources.fetch_opensky_departures(row["icao"], min(int(days), 7))
    mix = scoring.route_mix(flights, row["icao"], coords, long_haul_miles)
    bts_avg_distance = round(float(row["avg_stage_miles"]))

    if mix["flights_analyzed"] == 0:
        return {
            "airport": code, "status": "NO_DATA",
            "instruction": "The long-haul share CANNOT be computed: no observed flights available. "
                           "Do NOT report 0%. Tell the user the data is missing and why.",
            "notes": notes,
            "bts_avg_flight_distance_miles_12m": bts_avg_distance,
            "bts_note": "Average distance is a mean across all flights (incl. cargo); it cannot give a share.",
        }
    return {
        "airport": code, "icao": row["icao"],
        "source": "OpenSky Network ADS-B departures (sample of observed flights), great-circle distance",
        "days_used": days_used, "notes": notes, **mix,
        "bts_avg_flight_distance_miles_12m": bts_avg_distance,
        "caveats": [
            "OpenSky is crowd-sourced coverage: flights with no detected destination are excluded.",
            "Includes cargo flights; see the 'excluding known cargo operators' figure.",
            f"Long-haul threshold is an assumption ({long_haul_miles:.0f} mi); ask to change it.",
        ],
    }


def monthly_trend(code: str) -> dict:
    data, _, _ = load_data()
    code, row = find_airport_row(code)
    if row is None:
        return {"error": f"{code} not found."}
    months = data["monthly"][data["monthly"]["airport"] == code].sort_values("month")
    return {"airport": code, "months": [
        {"month": f"{m.month:%Y-%m}", "passengers": int(m.pax), "seats": int(m.seats),
         "load_factor_pct": round(100 * m.pax / m.seats, 1) if m.seats else None}
        for m in months.itertuples()]}


# ---------- registry for the agent ----------

FUNCTIONS = {f.__name__: f for f in [find_airports, rank_airports, compare_airports,
                                     analyze_unmet_demand, route_distance_mix, monthly_trend]}

AIRPORT_CODE = {"type": "string", "description": "IATA code, e.g. SFO (ICAO like KSFO also accepted)"}

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
            "code": AIRPORT_CODE, "target_load_factor": {"type": "number", "default": 0.8}},
            "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "route_distance_mix",
        "description": "Share of short/medium/long-haul departures from an airport, from observed flights "
                       "(OpenSky). Use for long-haul percentage questions.",
        "parameters": {"type": "object", "properties": {
            "code": AIRPORT_CODE, "long_haul_miles": {"type": "number", "default": config.LONG_HAUL_MILES},
            "days": {"type": "integer", "default": config.OPENSKY_DAYS}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "monthly_trend",
        "description": "Monthly passengers, seats and load factor for the last 24 months for one airport.",
        "parameters": {"type": "object", "properties": {"code": AIRPORT_CODE}, "required": ["code"]}}},
]


def run_tool(name: str, args: dict) -> dict:
    """Run a tool by name. Errors are returned to the LLM instead of crashing the chat."""
    if name not in FUNCTIONS:
        return {"error": f"unknown tool {name}"}
    try:
        return FUNCTIONS[name](**(args or {}))
    except Exception as error:
        return {"error": f"{type(error).__name__}: {error}"}


if __name__ == "__main__":  # quick check without the LLM
    print(json.dumps(rank_airports(region="New England", top_n=5), indent=2))
    print(json.dumps(compare_airports(["LAX", "SNA"]), indent=2))
    print(json.dumps(analyze_unmet_demand("SFO"), indent=2))
