# HANDOFF - read this first when resuming

**Team:** Adir (lead, runs everything locally) · Claude (plan + build) · Gemini (review / architecture)
**Deadline:** 24h from task receipt (Adir owns the clock)

## Status
| Milestone | State |
|---|---|
| M0 Scaffold (docs, config, sync files) | done |
| M1 Data layer (`data_sources.py`) | code done, **needs first real run on Adir's Mac** |
| M2 Scoring + tests (`scoring.py`, `tests/`) | done, 4 tests pass (synthetic data) |
| M3 Agent (`tools.py`, `agent.py`, `cli.py`) | code done, tested with mocked LLM; **needs real LLM run** |
| M4 UI (`app.py`) | done, headless-tested with mocked agent |
| M5 Docs (`docs/DESIGN.md`, README, sample answers) | draft; finalize after real numbers |

## Next steps
1. Adir: `python data_sources.py --refresh` → paste output (sanity-check numbers, BTS lag).
2. Adir: add Groq key to `.env` → `python cli.py --samples` → paste output.
3. Adir (optional): OpenSky client in `.env` → `python data_sources.py --opensky` to cache Anchorage days.
4. Tune thresholds if numbers look off; finalize DESIGN.md; record sample answers.
5. Bonus if time: voice input (Streamlit audio input + Groq Whisper).

## Open questions / risks
- BTS: do latest months include complete international data? (check SFO monthly output)
- OpenSky: destination coverage for Asia-bound flights from ANC may be low → reported as coverage %.
- Groq free-tier token-per-minute limit → tool outputs are kept compact.
