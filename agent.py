"""The agent loop: the LLM picks tools and explains their results. It never computes numbers itself."""
from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

import config
import tools

load_dotenv()

SYSTEM_PROMPT = f"""You are an airport investment analyst assistant for a firm that funds US airport
modernization projects. You help analysts identify airports where renovations would be most profitable,
based on increased flight and passenger capacity.

HOW YOU WORK
- For any data question, call the tools. Every number you state MUST appear in a tool result in this
  conversation. Never invent, estimate or recall figures from memory, and do not do your own arithmetic
  (no derived totals, percentages or "top X%" claims) - quote the tool's numbers. If no tool covers it,
  say so and suggest the closest proxy the tools do offer.
- Missing data is NOT zero. If a tool returns an error or status NO_DATA, say the question cannot be
  answered with the available data and explain why. Never draw conclusions from missing data.
- When ranking, mention airport size (enplanements) so small and large airports are not confused.
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
HISTORY_MESSAGES = 4  # last 2 question/answer pairs: enough for follow-ups, fits free-tier limits


def create_client() -> tuple[OpenAI, str]:
    key = os.getenv("LLM_API_KEY")
    if not key:
        raise RuntimeError("LLM_API_KEY is missing. Copy .env.example to .env and add your key.")
    base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    model = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    # max_retries: on a rate-limit error (429) the SDK waits and retries by itself
    return OpenAI(api_key=key, base_url=base_url, max_retries=5), model


def call_llm(client: OpenAI, model: str, messages: list[dict]):
    """One LLM call. If the rate limit still blocks us after retries, use the fallback model.
    Returns (response, model that answered)."""
    request = dict(messages=messages, tools=tools.SCHEMAS, tool_choice="auto", temperature=0.1)
    try:
        return client.chat.completions.create(model=model, **request), model
    except RateLimitError:
        fallback = os.getenv("LLM_FALLBACK_MODEL", "openai/gpt-oss-20b")
        if not fallback or fallback == model:
            raise
        return client.chat.completions.create(model=fallback, **request), fallback


def ask(history: list[dict]) -> tuple[str, list[dict]]:
    """Answer the last user message.
    history: [{"role": "user" or "assistant", "content": text}, ...]
    Returns (answer in markdown, trace = every tool call with its arguments and result)."""
    client, model = create_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history[-HISTORY_MESSAGES:]
    trace = []
    fallback_used = None

    for _ in range(MAX_STEPS):  # each step: the LLM either asks for tools or gives the final answer
        response, answered_by = call_llm(client, model, messages)
        if answered_by != model:
            fallback_used = answered_by
        message = response.choices[0].message

        if not message.tool_calls:  # final answer
            answer = message.content or ""
            if fallback_used:
                answer += f"\n\n_(Answered with fallback model {fallback_used} due to rate limits.)_"
            return answer, trace

        # The LLM asked for tools: run each one and send the results back
        messages.append({"role": "assistant", "content": message.content or "", "tool_calls": [
            {"id": call.id, "type": "function",
             "function": {"name": call.function.name, "arguments": call.function.arguments}}
            for call in message.tool_calls]})
        for call in message.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.run_tool(call.function.name, args)
            trace.append({"tool": call.function.name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": json.dumps(result, default=str, separators=(",", ":"))})

    return "I could not finish within the tool-call limit. Please narrow the question.", trace
