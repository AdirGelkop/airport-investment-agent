# Submission notes (paste into the "notes" box)

Hi, thanks for the assignment - it was fun to build.

**Repo:** https://github.com/AdirGelkop/airport-investment-agent
**Run (Python 3.9+):** `pip install -r requirements.txt` → `cp .env.example .env` (add a free Groq key) → `streamlit run app.py`.
Data is cached in the repo, so no data download or other accounts are needed.

**Approach in one line:** the LLM understands the question and explains; all numbers come from public data and
deterministic, unit-tested Python scoring.

- **Data (public APIs):** BTS T-100 via data.bts.gov (monthly passengers, seats, departures per airport, through Apr 2026),
  OurAirports (location, runways), OpenSky Network (observed flights with destinations, for long-haul share).
- **Scoring:** Expansion Score (0-100) = weighted national percentiles of passenger volume, load factor, passenger growth,
  demand-vs-seat-supply gap and runway strain. Also a Congestion Index and an unmet-demand estimate (seats needed to reach
  an 80% load factor). All weights/thresholds live in `config.py`.
- **Transparency:** every answer ends with assumptions & uncertainty, and has a "Data & calculations" panel showing the exact
  tool calls and numbers.
- **Guardrails:** the LLM may not state numbers that are not in a tool result; missing data is reported as missing, never as zero.

**Docs:** `docs/DESIGN.md` (methodology, tradeoffs, where AI is used), `docs/SAMPLES.md` (answers to the 4 example questions
+ a follow-up), `DECISIONS.md` (short decision log).

**Main assumptions / limits:** no public data on gates, terminal size or costs, so demand-pressure proxies are used;
BTS data lags ~5 months; OpenSky is a 7-day observed sample (~79% destination coverage at ANC).

**AI use while building:** I used AI assistants (Claude for implementation, Gemini for design review). I led the
work, made the design decisions, and ran and checked the results on real data.
