# Airport Investment Intelligence Agent

Chat agent that helps analysts find US airports where adding terminal / flight capacity is most likely to pay off.
Numbers come from **public APIs + deterministic Python scoring**; the LLM only picks tools and explains results.

See **[docs/DESIGN.md](docs/DESIGN.md)** for scoring methodology, tradeoffs and where AI is used.

## Quick start (macOS / Linux, Python 3.9+)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then put your free Groq key in LLM_API_KEY
streamlit run app.py          # opens http://localhost:8501
```
The repo ships with a data cache (`data/cache/`), so the app runs without any data download.
To refresh from the live APIs: `python data_sources.py --refresh`.

Other entry points:
- `python cli.py` - terminal chat; `python cli.py --samples` runs the 4 example questions
- `python tools.py` - runs the scoring tools directly (no LLM, no key needed)
- `python -m pytest -q` - unit tests for the scoring logic

## Example questions
- Which airports in New England are strong candidates for terminal expansion?
- Compare LA and Santa Ana airport congestion levels.
- What is the percentage of long haul flights out of Anchorage airport?
- What is the unmet flight demand in SFO airport and why?
- Follow-ups: "Why is BDL ranked above PVD?", "Use 3,000 miles as long-haul instead", "Show SFO's monthly trend".

## Project layout
| File | Role |
|---|---|
| `data_sources.py` | Fetch + cache public data (BTS T-100, OurAirports, OpenSky) |
| `scoring.py` | Deterministic KPIs, Expansion Score, Congestion Index, unmet demand, route mix |
| `config.py` | All weights, thresholds and region definitions in one place |
| `tools.py` | The 6 functions the LLM may call (JSON in/out) |
| `agent.py` | LLM tool-calling loop + system prompt (rules: no invented numbers, state assumptions) |
| `app.py` | Streamlit chat UI with an audit panel per answer |
| `cli.py` | Terminal chat / sample runner |
| `tests/` | Unit tests on synthetic data |

## Optional: live OpenSky data
Long-haul questions use observed flights from OpenSky Network. Cached days are included; to fetch new days,
create a free OpenSky account → Account → API client, and put the client id/secret in `.env`.
