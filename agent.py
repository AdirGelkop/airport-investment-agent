"""LLM tool-calling loop. The LLM chooses tools and explains results; it never computes numbers itself."""
from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI

import config
import tools

load_dotenv()

SYSTEM_PROMPT = f"""You are an airport investment analyst assistant for a firm that funds US airport
modernization projects. You help analysts find airports where adding terminal / flight capacity is most
likely to pay off.

HOW YOU WORK
- For any data question, call the tools. Every number you state MUST come from a tool result in this
  conversation. Never invent, estimate or recall figures from memory. If no tool covers it, say so and
  suggest the closest proxy the tools do offer.
- If a city or airport name is ambiguous, call find_airports and state which airport you chose
  (e.g. "LA" = LAX). If a region is named, use rank_airports with that region.
- For follow-up questions, reuse numbers already shown or call tools again (e.g. change a threshold).

HOW YOU ANSWER (keep it concise, analyst style)
1. Direct answer in 1-2 sentences.
2. Key numbers (a small markdown table when comparing or ranking).
3. Why: the KPIs that drove the result (use the tool's strengths/weaknesses/signals).
4. "Assumptions & uncertainty": data window, source, proxies used, and anything the data cannot show.

METHODOLOGY (for explaining, do not recompute)
- Expansion Score 0-100 = weighted national percentile ranks among US airports with >= {config.MIN_ENPLANEMENTS:,}
  yearly enplanements: {", ".join(f"{k} {int(v*100)}%" for k, v in config.EXPANSION_WEIGHTS.items())}.
- Congestion Index 0-100 = average percentile of load factor, peak-month load factor, movements per runway.
- Unmet demand = extra seats needed to bring the 12-month load factor to {config.TARGET_LOAD_FACTOR:.0%}.
- Scope: US airports, BTS T-100 data (lags ~5 months), OpenSky for observed routes. No data on gates,
  terminal size, construction cost, fares or airport finances: say so if asked.
"""

MAX_STEPS = 6


def _client() -> Tuple[OpenAI, str]:
    key = os.getenv("LLM_API_KEY")
    if not key:
        raise RuntimeError("LLM_API_KEY is missing. Copy .env.example to .env and add your key.")
    base = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
    return OpenAI(api_key=key, base_url=base), model


def ask(history: List[Dict[str, str]]) -> Tuple[str, List[Dict]]:
    """history = [{"role": "user"|"assistant", "content": str}, ...] (text only, keeps tokens low).
    Returns (answer_markdown, trace) where trace lists every tool call with args and result."""
    client, model = _client()
    messages: List[Dict] = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-10:]
    trace: List[Dict] = []

    for _ in range(MAX_STEPS):
        resp = client.chat.completions.create(
            model=model, messages=messages, tools=tools.SCHEMAS, tool_choice="auto", temperature=0.1)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return msg.content or "", trace

        messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.run_tool(tc.function.name, args)
            trace.append({"tool": tc.function.name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, default=str)})

    return "I could not finish within the tool-call limit. Please narrow the question.", trace
