"""Terminal chat for quick testing:  python cli.py   (type 'exit' to quit)
Or run the 4 sample questions:       python cli.py --samples"""
import json
import sys

import agent

SAMPLES = [
    "Which airports in New England are strong candidates for terminal expansion?",
    "Compare LA and Santa Ana airport congestion levels.",
    "What is the percentage of long haul flights out of Anchorage airport?",
    "What is the unmet flight demand in SFO airport and why?",
]


def turn(history, q):
    history.append({"role": "user", "content": q})
    answer, trace = agent.ask(history)
    history.append({"role": "assistant", "content": answer})
    print("\n[tools] " + "; ".join(f"{t['tool']}({json.dumps(t['args'])})" for t in trace))
    print("\n" + answer + "\n" + "-" * 80)


if __name__ == "__main__":
    history = []
    if "--samples" in sys.argv:
        for q in SAMPLES:
            print("\n>>> " + q)
            turn([], q)
        sys.exit()
    while True:
        q = input("\nYou: ").strip()
        if q.lower() in {"exit", "quit"}:
            break
        if q:
            turn(history, q)
