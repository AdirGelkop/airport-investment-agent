# HANDOFF - read this first when resuming

**Team:** Adir (lead, runs everything locally) · Claude (plan + build) · Gemini (review / architecture)
**Deadline:** 24h from task receipt (Adir owns the clock)
**Repo:** github.com/AdirGelkop/airport-investment-agent (public; Claude GitHub App installed → Claude can push)
**Local path (Adir):** /Users/adirgelkop/Desktop/Everything/Assignments/airport-investment-agent

## Status
| Milestone | State |
|---|---|
| M0 Scaffold | done |
| M1 Data layer | done; cache committed (BTS May 2025-Apr 2026, OurAirports, OpenSky ANC 17-23 Sep 2026) |
| M2 Scoring + tests | done; signals calibrated to national percentiles |
| M3 Agent | done; real run OK with Groq `openai/gpt-oss-120b` (llama-3.3-70b not on free tier) |
| M4 UI | code done; **needs real run by Adir** (`streamlit run app.py`) |
| M5 Docs | DESIGN.md draft; finalize + sample answers + submission notes |

## Key real-data results (for sanity)
- New England top 5: BGR, PWM, BTV, BOS, BDL (BOS 4th: scale weight only 20% - judgment call).
- LAX Congestion 90.3 vs SNA 78.8 (371 vs 283 movements/runway/day).
- SFO unmet: ~1.03M seats/yr ≈ 16.6 daily departures to reach 80% LF.
- ANC long-haul (≥2,500 mi): 54.4% of airline flights; 35.9% excl. known cargo operators; 79% destination coverage.

## Fixed after first real LLM run
- LLM said "0% long-haul" when data was missing → tool now returns NO_DATA; prompt: missing ≠ zero.
- LLM invented seat totals for SFO → tool returns totals; prompt forbids own arithmetic.

## Rate limits (Groq free tier: 8K tokens/min on gpt-oss-120b)
- SDK auto-retries 429s (max_retries=5); then falls back to `LLM_FALLBACK_MODEL` (gpt-oss-20b, separate quota).
- Only last 2 exchanges sent as history; compact JSON tool results.

## Next steps
1. Adir: `streamlit run app.py`, run 4 samples + 1-2 follow-ups; report issues.
2. Gemini review of DESIGN.md + scoring weights.
3. Finalize DESIGN.md, record sample answers (docs/SAMPLES.md), write submission notes.
4. Bonus if time: voice input (Streamlit audio input + Groq Whisper).
