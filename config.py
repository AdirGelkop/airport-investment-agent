"""All tunable assumptions in one place: data sources, weights, thresholds, regions."""

# Data sources (public; only OpenSky needs a free account)
BTS_ENDPOINT = "https://data.bts.gov/resource/r495-tyji.json"  # BTS T-100 summary by origin airport
OURAIRPORTS_AIRPORTS = "https://davidmegginson.github.io/ourairports-data/airports.csv"
OURAIRPORTS_RUNWAYS = "https://davidmegginson.github.io/ourairports-data/runways.csv"
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
)
OPENSKY_API = "https://opensky-network.org/api"

# Which airports are compared: FAA "primary" airports have over 10,000 enplanements a year
MIN_ENPLANEMENTS = 10_000
MIN_RUNWAY_LENGTH_FT = 3_000  # ignore helipads and very short strips

# Expansion Score = weighted average of national percentiles (weights sum to 1)
EXPANSION_WEIGHTS = {
    "scale": 0.20,          # passenger volume
    "load_factor": 0.25,    # how full the flights are
    "pax_growth": 0.20,     # passenger growth, last 12 months vs prior 12
    "supply_gap": 0.20,     # passenger growth minus seat growth
    "runway_strain": 0.15,  # aircraft movements per runway per day
}

# Congestion Index = simple average of these percentiles
CONGESTION_COMPONENTS = ["load_factor", "peak_load_factor", "runway_strain"]

# Unmet demand
TARGET_LOAD_FACTOR = 0.80  # seats are "enough" when flights are 80% full
HIGH_PERCENTILE = 80       # a signal is "high" when it is in the national top 20%

# Route distance (statute miles)
LONG_HAUL_MILES = 2_500    # about 4,000 km
SHORT_HAUL_MILES = 800
OPENSKY_DAYS = 7

# Callsign prefixes of known all-cargo airlines (not a complete list)
CARGO_CALLSIGN_PREFIXES = {
    "FDX", "UPS", "GTI", "CKS", "CLX", "NCA", "ABX", "ATN", "PAC", "CKK", "CAO",
    "AER", "NAC", "ABW", "BCS", "BOX", "GEC", "MPH", "SQC", "WGN", "NCR", "KYE", "CSS", "YZR", "AHK",
}

# Regions = US Census divisions, plus "West Coast"
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
