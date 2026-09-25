"""Every tunable assumption lives here, so the scoring logic is easy to audit and change."""

# ---------- Data sources (public, no key needed except OpenSky) ----------
# BTS "AFF - T100 Segment Summary By Origin Airport" (monthly, per US origin airport)
BTS_ENDPOINT = "https://data.bts.gov/resource/r495-tyji.json"
OURAIRPORTS_AIRPORTS = "https://davidmegginson.github.io/ourairports-data/airports.csv"
OURAIRPORTS_RUNWAYS = "https://davidmegginson.github.io/ourairports-data/runways.csv"
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
)
OPENSKY_API = "https://opensky-network.org/api"

# ---------- Scope ----------
# FAA "primary" commercial-service airports have > 10,000 enplanements per year.
# Only these airports form the comparison universe for percentiles.
MIN_ENPLANEMENTS = 10_000
MIN_RUNWAY_LENGTH_FT = 3_000  # ignore helipads / very short strips when counting runways

# ---------- Expansion Score (0-100) ----------
# Weighted average of percentile ranks vs. all US primary airports.
EXPANSION_WEIGHTS = {
    "scale": 0.20,          # passenger volume (bigger base = bigger revenue pool)
    "load_factor": 0.25,    # how full flights are (demand pressing on capacity)
    "pax_growth": 0.20,     # passenger momentum, last 12m vs prior 12m
    "supply_gap": 0.20,     # passenger growth minus seat growth (demand outpacing supply)
    "runway_strain": 0.15,  # est. aircraft movements per runway per day
}

# Congestion Index (0-100) = simple average of these percentile ranks
CONGESTION_COMPONENTS = ["load_factor", "peak_load_factor", "runway_strain"]

# ---------- Unmet-demand logic ----------
TARGET_LOAD_FACTOR = 0.80   # "comfortable" load factor used to size missing capacity
HIGH_PERCENTILE = 80        # signal thresholds are relative: "top 20% nationally"

# ---------- Route distance ----------
# Long-haul default ~ 4,000 km (Eurocontrol-style market segment), in statute miles.
LONG_HAUL_MILES = 2_500
SHORT_HAUL_MILES = 800
OPENSKY_DAYS = 7

# ICAO callsign prefixes of well-known all-cargo operators (used only to show a
# "excluding known cargo operators" split; not exhaustive).
CARGO_CALLSIGN_PREFIXES = {
    "FDX", "UPS", "GTI", "CKS", "CLX", "NCA", "ABX", "ATN", "PAC", "CKK", "CAO",
}

# ---------- Regions (US Census divisions + a few common names) ----------
REGIONS = {
    "New England": ["CT", "ME", "MA", "NH", "RI", "VT"],
    "Mid-Atlantic": ["NJ", "NY", "PA"],
    "East North Central": ["IL", "IN", "MI", "OH", "WI"],
    "West North Central": ["IA", "KS", "MN", "MO", "NE", "ND", "SD"],
    "South Atlantic": ["DE", "DC", "FL", "GA", "MD", "NC", "SC", "VA", "WV"],
    "East South Central": ["AL", "KY", "MS", "TN"],
    "West South Central": ["AR", "LA", "OK", "TX"],
    "Mountain": ["AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY"],
    "Pacific": ["AK", "CA", "HI", "OR", "WA"],
    "West Coast": ["CA", "OR", "WA"],
}
