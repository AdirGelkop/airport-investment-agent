# Sample answers (generated 2026-09-25, model openai/gpt-oss-120b)

Produced by `python cli.py --samples --save docs/SAMPLES.md`. Numbers come from tools; the LLM wrote the text.



> **Audit note (by us, after generation):** every number in the tables and headline answers was checked
> against the tool output shown in the app's "Data & calculations" panel and is correct. Two minor LLM
> paraphrasing errors were found and are left visible on purpose:
> 1. New England: the text says three airports show demand outpacing supply; the tool data shows four (BDL too).
> 2. Anchorage follow-up (first answer): "≈ 26 % of raw records" without a destination is not a tool figure;
>    the tool reports 365 of 2,730 flights without a known destination and 79.4 % destination coverage.
> This is the residual risk described in DESIGN.md §8.

---

## Q: Which airports in New England are strong candidates for terminal expansion?

*Tools called:* `rank_airports({"region": "New England", "sort_by": "expansion_score"})`

**Answer**  
The strongest New England airports for a terminal‑capacity investment are, in order of their Expansion Score, Bangor (BGR), Portland‑ME (PWM), Burlington (BTV), Boston Logan (BOS) and Bradley (BDL). All five rank in the top 35 of 399 U.S. airports and combine high load factors, solid passenger volumes and, for most, demand that outpaces seat supply.

**Key KPIs (May 2025 – Apr 2026)**  

| Rank | IATA | Airport (city, state) | 12‑mo enplanements | Expansion Score | Congestion Index |
|------|------|-----------------------|-------------------|----------------|-----------------|
| 1 | BGR | Bangor International (Bangor, ME) | 441 517 | 74.3 | 78.1 |
| 2 | PWM | Portland International Jetport (Portland, ME) | 1 277 351 | 73.6 | 86.9 |
| 3 | BTV | Patrick Leahy Burlington Intl (Burlington, VT) | 702 627 | 72.5 | 82.9 |
| 4 | BOS | Boston Logan Intl (Boston, MA) | 20 983 745 | 71.1 | 83.1 |
| 5 | BDL | Bradley Intl (Hartford, CT) | 3 251 263 | 70.8 | 80.0 |

**Why these airports stand out**

* **Expansion Score drivers** – The score is a weighted national percentile of (1) passenger volume, (2) load factor, (3) passenger growth, (4) demand‑supply gap, and (5) runway‑strain. All five airports score in the top 25 % for load factor (≈ 80 %+), and three (BGR, PWM, BTV) also show positive passenger growth or a clear demand‑out‑of‑supply signal.
* **Congestion** – Their Congestion Indexes (≈ 78‑87) indicate that existing facilities are operating near capacity, especially on peak months (e.g., PWM’s peak‑month load factor 88.9 %).
* **Runway strain** – Even with multiple runways, movements per runway per day are high (e.g., BOS 207.9, BDL 84.7), suggesting limited runway capacity to absorb additional flights without terminal expansion.
* **Size context** – Enplanement figures range from ~0.44 M (BGR) to ~21 M (BOS), so the list includes both a midsize regional hub (BGR) and the largest New England gateway (BOS), ensuring that investment opportunities exist across the market‑size spectrum.

**Assumptions & uncertainty**

* **Data window** – All KPIs are drawn from BTS T‑100 data for the 12‑month period May 2025 – Apr 2026 (≈ 5‑month lag) and runway counts from OurAirports.
* **Scope** – Only commercial‑passenger metrics are available; gate counts, terminal square‑footage, construction cost estimates, fare structures and airport financials are not included.
* **Proxies** – “Demand outpacing seat supply” is inferred from the seat‑growth vs. passenger‑growth percentages and the load‑factor percentile; it does not capture airline‑specific capacity decisions.
* **Missing data** – No airport in the region returned a “NO_DATA” status, so the ranking reflects the full set of New England airports with ≥ 10 000 enplanements.


---

## Q: Compare LA and Santa Ana airport congestion levels.

*Tools called:* `find_airports({"query": "Los Angeles"}); compare_airports({"codes": ["LAX", "SNA"]})`

**Answer**  
- Los Angeles International (LAX) has a higher congestion level (Congestion Index ≈ 90) than John Wayne (Santa Ana – SNA, Congestion Index ≈ 79).  

**Key numbers**

| Airport | Enplanements (12 mo) | Congestion Index | Load factor % | Peak‑month load factor % | Movements per runway / day |
|---------|---------------------|------------------|---------------|--------------------------|----------------------------|
| LAX (Los Angeles) | 36,590,656 | **90.3** | 82.1 | 87.4 (Jun 2025) | 371.0 |
| SNA (Santa Ana)   | 5,590,354  | **78.8** | 80.4 | 83.8 (Jul 2025) | 282.8 |

**Why**  
- The Congestion Index combines three percentile‑based signals: overall load factor, peak‑month load factor, and movements per runway. LAX scores higher on each (load factor 82 % vs 80 %, peak‑month 87 % vs 84 %, and 371 vs 283 movements per runway), driving its higher overall index.  

**Assumptions & uncertainty**  
- Data cover May 2025 – Apr 2026 (compared to the prior 12 months).  
- Only BTS T‑100 commercial traffic and runway counts are used; gate capacity, terminal size, or weather‑related delays are not reflected.  
- No missing data for the requested KPIs; the indices are derived directly from the tool output.


---

## Q: What is the percentage of long haul flights out of Anchorage airport?

*Tools called:* `route_distance_mix({"code": "ANC", "days": 7, "long_haul_miles": 2500})`

**Answer**  
≈ 54 % of observed departures from Anchorage (ANC) are long‑haul (≥ 2 500 mi).

| KPI | Value |
|-----|-------|
| Long‑haul share (≥ 2 500 mi) | **54.4 %** |
| Total flights analyzed (7 days) | 1 408 |
| Short‑haul share | 25.6 % |
| Medium‑haul share | 20.0 % |

**Why** – The OpenSky Network sample of airline departures over the past week shows that 54.4 % of the 1 408 analyzed flights exceed the 2 500‑mile threshold, indicating a strong long‑haul component at ANC.

**Assumptions & uncertainty**  
- Data are from a 7‑day OpenSky sample (Sept 17‑23 2026) and cover only flights with a detected destination (≈ 79 % coverage).  
- Cargo flights are included; excluding known cargo operators reduces the long‑haul share to 35.9 %.  
- The long‑haul definition (≥ 2 500 mi) is user‑set; changing it would alter the percentage.


---

## Q: What is the unmet flight demand in SFO airport and why?

*Tools called:* `analyze_unmet_demand({"code": "SFO"})`

**Unmet flight demand at SFO:** ≈ 1.03 million seats per year, or about **16.6 additional daily departures** would be needed to bring the 12‑month load factor down to the target 80 %.

| KPI | Value |
|-----|-------|
| 12‑month load factor (actual) | **82.6 %** |
| Target load factor | 80 % |
| Seats offered (12 mo) | 32,273,396 |
| Seats needed for 80 % LF | 33,303,256 |
| **Extra seats required** | **1,029,860** |
| Avg. seats per departure | 170 |
| **Extra daily departures** | **16.6** |

**Why the demand is unmet**

- **High load factor:** SFO’s flights are 82.6 % full, ranking above 92 % of U.S. airports, leaving little spare capacity.
- **Seasonal peak pressure:** June 2025 peaked at 89.4 % load factor (top‑20% nationally), indicating acute seasonal crunch.
- **Supply‑side constraints:** ≈ 261 movements per runway per day (top‑20% nationally) and only four runways limit the ability to add more flights.
- **Growth vs capacity:** Passenger growth (+3.4 %) matches seat growth (+3.4 %), so demand is not outpacing supply, but the current seat inventory still falls short of the 80 % target.

**Assumptions & uncertainty**

- **Data window:** May 2025 – Apr 2026 (compared to prior 12 months May 2024 – Apr 2025).  
- **Source:** BTS T‑100 segment data (enplaned passengers, seats, departures) and runway counts from OurAirports.  
- **Method:** Seats needed = passengers / 0.80 – seats offered; extra departures = extra seats / 170 / 365.  
- **Caveats:** The estimate is a proxy; BTS records only flown passengers, so it cannot capture passengers who were turned away or chose another airport. Avg. seats per departure includes cargo flights, which may slightly overstate the required number of additional departures. Movements per runway count only commercial BTS‑reporting flights, omitting GA/military traffic.


---

## Q: What is the percentage of long haul flights out of Anchorage airport?

*Tools called:* `route_distance_mix({"code": "ANC"})`

**Answer**  
≈ 54 % of observed departures from Anchorage (ANC) are long‑haul (≥ 2 500 mi).

| Metric | Value |
|--------|-------|
| Long‑haul share (all flights) | **54.4 %** |
| Long‑haul share (excluding known cargo operators) | 35.9 % |

**Why this figure**  
The OpenSky Network ADS‑B departure sample for the past 7 days (2 730 raw flights, 1 408 analyzed) shows that 54.4 % of the flights fall into the ≥ 2 500 mi distance band. This is the direct “long‑haul share” reported by the tool.

**Assumptions & uncertainty**  
- Data are a crowd‑sourced sample of observed commercial departures; flights without a detected destination (≈ 26 % of raw records) are excluded.  
- The long‑haul threshold is set at 2 500 mi (the default).  
- The figure includes cargo flights; when cargo operators are removed, the long‑haul share drops to 35.9 %.  
- The sample covers only the most recent 7 days, so short‑term variations may affect the percentage.


---

## Q: What if we define long-haul as 3,000 miles instead?

*Tools called:* `route_distance_mix({"code": "ANC", "days": 7, "long_haul_miles": 3000})`

**Answer**  
When “long‑haul” is defined as ≥ 3 000 mi, **≈ 36 %** of observed departures from Anchorage (ANC) fall into that category.

| Metric | Value |
|--------|-------|
| Long‑haul share (≥ 3 000 mi, all flights) | **36.0 %** |
| Long‑haul share (≥ 3 000 mi, excluding known cargo operators) | 22.1 % |
| Short‑haul (< 800 mi) | 25.6 % |
| Medium‑haul (800‑3 000 mi) | 38.4 % |

**Why**  
The OpenSky Network ADS‑B departure sample for the most recent 7 days (1 408 analyzed flights) shows that 36.0 % of flights travel ≥ 3 000 mi. This is the direct “long‑haul share” reported by the tool.

**Assumptions & uncertainty**  
- Only flights with a detected destination are counted (79.4 % coverage).  
- The long‑haul threshold is set at 3 000 mi (the value you requested).  
- Cargo flights are included; removing known cargo operators reduces the share to 22.1 %.  
- The data represent a 7‑day snapshot, so short‑term fluctuations may affect the percentage.
