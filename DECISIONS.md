# Decisions log (short, one line of "why" each)

1. **Python + Streamlit** - fastest path to a working chat UI; one language end to end.
2. **LLM never computes numbers** - it picks tools and explains; all figures come from `scoring.py` (auditable, testable).
3. **OpenAI-compatible client** - default Groq free tier; Gemini/OpenRouter = change 3 lines in `.env`.
4. **BTS T-100 "Segment Summary by Origin Airport" (Socrata API)** - official, free, no key, monthly, all US airports.
5. **Window = last 12 months vs prior 12** - removes seasonality; BTS lags ~5 months (latest checked: Apr 2026).
6. **Percentile-based score vs national universe** (FAA primary: >10k enplanements) - comparable units, robust to outliers, works for any subset (region, pair).
7. **Proxies stated openly** - no public API for gates/terminal size/costs; load factor, supply gap, runway strain are the proxies.
8. **OpenSky for long-haul share** - only public source with per-flight destinations; sample-based, so coverage is reported.
9. **Cache committed to repo** - reviewers can run without data downloads or OpenSky account.
10. **Text-only chat history to the LLM** - keeps tokens under free-tier limits; follow-ups re-call tools if needed.
11. **Python 3.9 compatible** - runs on macOS system Python without extra installs.
