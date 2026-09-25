# HANDOFF - read this first when resuming

**Team:** Adir (lead, runs everything locally) · Claude (plan + build) · Gemini (review / architecture)
**Repo:** github.com/AdirGelkop/airport-investment-agent (public; Claude GitHub App installed → Claude can push)
**Local path (Adir):** /Users/adirgelkop/Desktop/Everything/Assignments/airport-investment-agent
**Deadline:** 24h from task receipt (Adir owns the clock)

## Checklist
### Done
- [x] Data layer: BTS T-100 (May 2025-Apr 2026), OurAirports, OpenSky ANC (17-23 Sep 2026) - all cached in repo
- [x] Deterministic scoring + 4 unit tests (Expansion Score, Congestion Index, unmet demand, route mix)
- [x] Agent: 6 tools, Groq `openai/gpt-oss-120b`, fallback `gpt-oss-20b`, retries on rate limits
- [x] Guardrails: NO_DATA ≠ 0, no LLM arithmetic, assumptions section in every answer
- [x] Streamlit chat UI with "Data & calculations" audit panel - tested by Adir (~8 rapid questions OK)
- [x] Gemini architecture review - approved; scale weight 20% kept on purpose (documented)
- [x] docs: DESIGN.md (methodology, tradeoffs, AI use, verification), SAMPLES.md, SUBMISSION_NOTES.md, README

### Remaining (must)
- [ ] Final read-through of DESIGN.md + SUBMISSION_NOTES.md by Adir (can he explain every line?)
- [ ] Submit: upload files (or repo zip) + paste docs/SUBMISSION_NOTES.md into the notes box

### Optional (bonus)
- [ ] Voice input (Streamlit audio input → Groq Whisper → same agent)

## Key real-data results
- New England top 5: BGR, PWM, BTV, BOS, BDL.
- LAX Congestion 90.3 vs SNA 78.8 (371 vs 283 movements/runway/day).
- SFO unmet: ~1.03M seats/yr ≈ 16.6 daily departures to reach 80% LF.
- ANC long-haul (≥2,500 mi): 54.4% (35.9% excl. known cargo); at 3,000 mi: 36.0%.

## How to resume (any of us)
- Adir: `cd <local path> && git pull && source .venv/bin/activate && streamlit run app.py`
- Claude / Gemini: read this file, then `docs/DESIGN.md`; code map is in README.md.
- Everything tunable is in `config.py`; every number the agent states comes from `scoring.py` via `tools.py`.

## Interview prep (likely questions)
- Why percentiles and these weights? → comparable units; judgment call; config.py; min_passengers filter.
- Why is BGR above BOS? → growth + full flights + supply gap; scale only 20% by design.
- How do you stop hallucinated numbers? → tools compute; prompt rules; NO_DATA; audit panel; residual risk stated.
- What would you do with more time? → delay data, FAA capacity data, number-verification check, analyst weight tuning.
