"""Unit tests for the deterministic scoring logic (synthetic data - no network needed)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scoring  # noqa: E402


def _synthetic():
    months = pd.date_range("2024-05-01", "2026-04-01", freq="MS")
    spec = {  # code: (pax/month prev year, pax growth, seats/month prev, seat growth)
        "AAA": (100_000, 0.20, 110_000, 0.05),  # busy, full, demand outpacing supply
        "BBB": (100_000, 0.00, 140_000, 0.00),  # flat, lots of empty seats
        "CCC": (20_000, -0.10, 25_000, 0.00),   # small, shrinking
    }
    rows = []
    for code, (pax, g, seats, sg) in spec.items():
        for i, mth in enumerate(months):
            cur = i >= 12
            rows.append({"airport": code, "month": mth,
                         "pax": pax * (1 + g) if cur else pax,
                         "seats": seats * (1 + sg) if cur else seats,
                         "deps": 1_000, "dist_x_deps": 1_000 * 900,
                         "dom_pax": 0.9 * pax, "freight_lbs": 0})
    monthly = pd.DataFrame(rows)
    base = pd.DataFrame({"airport": ["AAA", "BBB", "CCC"], "pax_2019": [1_500_000, 1_200_000, 300_000]})
    airports = pd.DataFrame({
        "code": ["AAA", "BBB", "CCC"], "name": ["A Intl", "B Intl", "C Rgnl"], "city": ["A", "B", "C"],
        "state": ["MA", "CT", "MA"], "icao": ["KAAA", "KBBB", "KCCC"],
        "lat": [42.0, 41.0, 42.5], "lon": [-71.0, -72.0, -71.5], "runways": [2, 2, 1]})
    return scoring.build_kpis(monthly, base, airports)


def test_kpi_math():
    k = _synthetic()
    a = k.loc["AAA"]
    assert a["pax"] == pytest.approx(12 * 120_000)
    assert a["load_factor"] == pytest.approx(120_000 / 115_500)
    assert a["pax_growth"] == pytest.approx(0.20)
    assert a["supply_gap"] == pytest.approx(0.20 - 0.05)
    assert a["movements_per_runway_day"] == pytest.approx(2 * 12_000 / 365 / 2)
    assert a["avg_stage_miles"] == pytest.approx(900)
    assert k.attrs["window"] == "May 2025-Apr 2026"


def test_ranking_is_deterministic_and_sensible():
    k1, k2 = _synthetic(), _synthetic()
    assert list(k1.sort_values("expansion_score", ascending=False).index) == \
           list(k2.sort_values("expansion_score", ascending=False).index)
    assert k1["expansion_score"].idxmax() == "AAA"
    assert k1["expansion_score"].between(0, 100).all()


def test_unmet_capacity():
    k = _synthetic()
    a = k.loc["AAA"]
    u = scoring.unmet_capacity(a, target_lf=0.80)
    expected_seats = a["pax"] / 0.80 - a["seats"]
    assert u["extra_annual_seats"] == round(expected_seats)
    assert scoring.unmet_capacity(k.loc["BBB"])["extra_annual_seats"] == 0  # LF 71% -> nothing missing
    assert any("outpacing" in s for s in scoring.unmet_signals(a))


def test_route_mix():
    coords = {"KLAX": (33.9425, -118.4081), "KJFK": (40.6398, -73.7789), "KSFO": (37.619, -122.375)}
    d = scoring.haversine_miles(*coords["KLAX"], *coords["KJFK"])
    assert 2_450 < d < 2_500  # LAX-JFK is ~2,475 statute miles
    flights = [
        {"callsign": "AAL100  ", "estArrivalAirport": "KJFK"},  # long (>= 2,400 threshold)
        {"callsign": "UAL200", "estArrivalAirport": "KSFO"},    # short
        {"callsign": "FDX300", "estArrivalAirport": "KJFK"},    # cargo, long
        {"callsign": "N123AB", "estArrivalAirport": "KSFO"},    # private -> excluded
        {"callsign": "DAL400", "estArrivalAirport": None},      # unknown -> excluded
    ]
    r = scoring.route_mix(flights, "KLAX", coords, long_haul_miles=2_400)
    assert r["flights_analyzed"] == 3
    assert r["long_haul_share_pct"] == pytest.approx(66.7)
    assert r["long_haul_share_excl_known_cargo_pct"] == pytest.approx(50.0)
    assert r["excluded_non_airline_callsign"] == 1
    assert r["excluded_unknown_destination"] == 1
