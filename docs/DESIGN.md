# Design - Airport Investment Intelligence Agent

## 1. Problem framing
An airport renovation pays off when it unlocks traffic that is **already there or clearly coming**:
lots of passengers, flights that are full, demand growing faster than the seats offered, and an airfield
that is busy. The agent turns that idea into transparent KPIs, ranks airports on them, and lets an analyst
interrogate the result in chat.

## 2. Architecture
```
 Streamlit chat (app.py) / CLI (cli.py)
            │  question + text history
            ▼
 agent.py  ── LLM (Groq, OpenAI-compatible) ── decides which tool(s) to call
            │  tool call (JSON args)                ▲ explains tool results
            ▼                                       │
 tools.py  ── 6 tools: find_airports, rank_airports, compare_airports,
            │         analyze_unmet_demand, route_distance_mix, monthly_trend
            ▼
 scoring.py ── deterministic KPIs, percentiles, scores (unit-tested)   config.py (all weights/thresholds)
            ▼
 data_sources.py ── public APIs → CSV/JSON cache (data/cache/)
     BTS T-100 (Socrata API) · OurAirports (CSV) · OpenSky Network (REST, OAuth2)
```
Every answer shows a **"Data & calculations"** panel with the exact tool calls and returned numbers.

## 3. Data sources
| Source | What we use | Notes |
|---|---|---|
| BTS T-100 Segment Summary by Origin Airport (data.bts.gov API) | Monthly enplaned passengers, seats, departures, avg flight distance, domestic vs total | Official DOT data, all US airports, ~5-month lag |
| BTS T-100 (2019) | Pre-pandemic passenger baseline | Recovery context |
| OurAirports | State, coordinates, runway count (open, ≥3,000 ft) | Community-maintained |
| OpenSky Network | Observed departures with destination airport | Sample-based ADS-B coverage; used for long-haul share |

## 4. Scoring methodology (deterministic)
Window: last 12 months of BTS data vs the prior 12 months (removes seasonality).
Universe: US airports with ≥ 10,000 yearly enplanements (FAA "primary" threshold).

| KPI | Formula | Why it matters |
|---|---|---|
| Scale | 12-month enplaned passengers | Size of the revenue pool |
| Load factor | passengers / seats | Full flights = demand pressing on capacity |
| Passenger growth | pax(12m) / pax(prior 12m) − 1 | Momentum |
| Supply gap | passenger growth − seat growth | Demand outpacing what airlines supply |
| Runway strain | 2 × departures / 365 / runways | Airfield busyness (proxy for congestion) |
| Peak-month load factor | max monthly LF in window | Seasonal crunch |

**Expansion Score (0-100)** = weighted average of national percentile ranks:
scale 20%, load factor 25%, passenger growth 20%, supply gap 20%, runway strain 15%.
Percentiles make different units comparable and keep one outlier from dominating.

**Congestion Index (0-100)** = average percentile of load factor, peak-month load factor, runway strain.

**Unmet demand** = seats needed to bring the 12-month load factor down to 80%
(`passengers / 0.80 − seats`), converted to daily flights with the airport's average seats per departure.
Explained by rule-based signals, relative to all US airports so thresholds stay calibrated: load factor,
peak-month load factor and runway strain in the national top 20%; passenger growth vs seat growth; traffic vs 2019.

**Long-haul share** = share of observed airline departures (OpenSky, last 7 days) whose great-circle distance
is ≥ 2,500 miles (~4,000 km). The threshold is a parameter the user can change in chat.

## 5. Where and how AI is used
- **LLM (Groq, openai/gpt-oss-120b by default)**: understands the question, resolves entities ("LA" → LAX),
  chooses tools and arguments, and writes the explanation with assumptions.
- **Not AI**: all numbers, rankings and scores (Python, unit-tested). The system prompt forbids stating any
  number that is not in a tool result, and requires an "Assumptions & uncertainty" section.
- Follow-ups: the chat history is sent back to the LLM, which can reuse earlier numbers or call tools again.

## 6. Key tradeoffs
| Choice | Gain | Cost |
|---|---|---|
| Proxies (LF, supply gap, runway strain) instead of terminal/gate capacity | Uses free, national, consistent data | No direct terminal capacity or cost data |
| Percentile scoring with fixed weights | Transparent, explainable, testable | Weights are judgment calls (all in `config.py`) |
| BTS T-100 monthly | Official and complete | ~5-month lag; not real-time |
| OpenSky sample for routes | Only free per-flight destination source | Coverage gaps; includes cargo; 7-day sample |
| Cached data in repo | Runs offline, reproducible demo | Needs `--refresh` to update |
| Text-only history to LLM | Fits free-tier token limits | LLM re-calls tools for detailed follow-ups |

## 7. Assumptions, uncertainty, scope
- Enplanements (departing passengers) represent airport demand; connecting vs local passengers are not separated.
- Flown passengers only: travelers who could not get a seat are invisible → unmet demand is a proxy.
- Runway counts from OurAirports; movements include only BTS-reporting carriers (no general aviation).
- Out of scope: construction cost, airport finances, fares, gate counts, local regulation.

## 8. Next steps (if continued)
Delay data (BTS on-time / FAA) in the Congestion Index · FAA enplanement & capacity reports ·
weight tuning with analysts · voice input · scenario analysis (e.g. "what if seats grow 10%").
