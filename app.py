"""Chat UI. Run with:  streamlit run app.py"""
import os

import pandas as pd
import streamlit as st
from openai import RateLimitError

import agent
import config
import scoring
import tools
from cli import SAMPLES

st.set_page_config(page_title="Airport Investment Agent", layout="wide")

# Runs just once - cache saving KPIs for all 399 airports
@st.cache_resource(show_spinner="Loading aviation data...")
def load_kpis():
    _, kpis, _ = tools.load_data()
    return kpis


kpis = load_kpis()
st.session_state.setdefault("messages", [])  # chat history: {"role", "content", "trace"}


# ---------- Sidebar: context, methodology, sample questions ----------
with st.sidebar:
    st.title("Airport Investment Agent")
    st.caption(f"Data window: **{kpis.attrs['window']}** · {kpis.attrs['universe_size']} US commercial airports")
    st.markdown(
        "**How it works**\n"
        "- Numbers come from public data (BTS T-100, OurAirports, OpenSky) and deterministic Python scoring.\n"
        "- The LLM only picks the right tool and explains the result.\n"
        "- Open *Data & calculations* under each answer to check it.")
    with st.expander("Scoring methodology"):
        st.markdown("**Expansion Score (0-100)**: weighted national percentiles")
        st.table(pd.DataFrame({"weight": config.EXPANSION_WEIGHTS}).rename(index=scoring.LABELS))
        st.markdown(f"**Congestion Index**: average percentile of load factor, peak-month load factor, "
                    f"movements per runway.\n\n**Unmet demand**: seats needed to reach a "
                    f"{config.TARGET_LOAD_FACTOR:.0%} load factor.")
    st.markdown("**Try:**")
    for sample in SAMPLES:
        if st.button(sample, use_container_width=True):
            st.session_state.pending = sample
    if st.button("New conversation", use_container_width=True):
        st.session_state.messages = []
    st.caption(f"Model: {os.getenv('LLM_MODEL', 'openai/gpt-oss-120b')}")

# Data & calculations window - showing 
def show_trace(trace):
    """The audit panel under an answer: every tool call, its arguments and its result."""
    with st.expander(f"Data & calculations ({len(trace)} tool calls)"):
        for step in trace:
            st.markdown(f"**`{step['tool']}`** `{step['args']}`")
            result = step["result"]
            table = result.get("results") or result.get("airports")
            if table:
                st.dataframe(pd.DataFrame(table), use_container_width=True)
            if step["tool"] == "monthly_trend" and result.get("months"):
                st.line_chart(pd.DataFrame(result["months"]).set_index("month")[["passengers", "seats"]])
            st.json(result, expanded=False)


# ---------- Chat ----------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("trace"):
            show_trace(message["trace"])

question = st.chat_input("Ask about US airports...") or st.session_state.pop("pending", None)
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
            trace = []
            try:
                answer, trace = agent.ask(history)
            except RateLimitError:
                answer = "The free LLM tier's per-minute limit was reached. Wait about 30 seconds and ask again."
            except Exception as error:
                answer = f"Error: {type(error).__name__}: {error}"
        st.markdown(answer)
        if trace:
            show_trace(trace)
    st.session_state.messages.append({"role": "assistant", "content": answer, "trace": trace})
