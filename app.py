"""Chat UI:  streamlit run app.py"""
import os

import pandas as pd
import streamlit as st

import agent
import config
import tools
from cli import SAMPLES

st.set_page_config(page_title="Airport Investment Agent", page_icon="✈️", layout="wide")


@st.cache_resource(show_spinner="Loading aviation data...")
def load():
    return tools._data()


_, kpis, _ = load()

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("✈️ Airport Investment Agent")
    st.caption(f"Data window: **{kpis.attrs['window']}** · {kpis.attrs['universe_size']} US commercial airports")
    st.markdown(
        "**How it works**\n"
        "- Numbers come from public data (BTS T-100, OurAirports, OpenSky) and deterministic Python scoring.\n"
        "- The LLM only picks the right tool and explains the result.\n"
        "- Open *Data & calculations* under each answer to audit it.")
    with st.expander("Scoring methodology"):
        st.markdown("**Expansion Score (0-100)**: weighted national percentiles")
        st.table(pd.DataFrame({"weight": config.EXPANSION_WEIGHTS}).rename(index=tools.scoring.LABELS))
        st.markdown(f"**Congestion Index**: average percentile of load factor, peak-month load factor, "
                    f"movements per runway.\n\n**Unmet demand**: seats needed to reach a "
                    f"{config.TARGET_LOAD_FACTOR:.0%} load factor.")
    st.markdown("**Try:**")
    for q in SAMPLES:
        if st.button(q, use_container_width=True):
            st.session_state.pending = q
    if st.button("🗑️ New conversation", use_container_width=True):
        st.session_state.messages = []
    st.caption(f"Model: {os.getenv('LLM_MODEL', 'llama-3.3-70b-versatile')}")

st.session_state.setdefault("messages", [])


def show_trace(trace):
    with st.expander(f"🔎 Data & calculations ({len(trace)} tool call{'s' if len(trace) != 1 else ''})"):
        for t in trace:
            st.markdown(f"**`{t['tool']}`** `{t['args']}`")
            res = t["result"]
            table = res.get("results") or res.get("airports")
            if table:
                st.dataframe(pd.DataFrame(table), use_container_width=True)
            if t["tool"] == "monthly_trend" and res.get("months"):
                st.line_chart(pd.DataFrame(res["months"]).set_index("month")[["passengers", "seats"]])
            st.json(res, expanded=False)


for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("trace"):
            show_trace(m["trace"])

question = st.chat_input("Ask about US airports...") or st.session_state.pop("pending", None)
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            try:
                answer, trace = agent.ask(history)
            except Exception as e:  # noqa: BLE001
                answer, trace = f"⚠️ {type(e).__name__}: {e}", []
        st.markdown(answer)
        if trace:
            show_trace(trace)
    st.session_state.messages.append({"role": "assistant", "content": answer, "trace": trace})
