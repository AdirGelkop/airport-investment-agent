"""Terminal chat for quick testing:  python cli.py   (type 'exit' to quit)
Run the 4 sample questions:          python cli.py --samples
...and save them as a markdown file: python cli.py --samples --save docs/SAMPLES.md"""
import json
import sys
from datetime import date

import agent

# SAMPLE Questions
SAMPLES = [
    "Which airports in New England are strong candidates for terminal expansion?",
    "Compare LA and Santa Ana airport congestion levels.",
    "What is the percentage of long haul flights out of Anchorage airport?",
    "What is the unmet flight demand in SFO airport and why?",
]
FOLLOW_UP = ("What is the percentage of long haul flights out of Anchorage airport?",
             "What if we define long-haul as 3,000 miles instead?")


def turn(history, q):
    history.append({"role": "user", "content": q})
    answer, trace = agent.ask(history)
    history.append({"role": "assistant", "content": answer})
    tools_line = "; ".join(f"{t['tool']}({json.dumps(t['args'])})" for t in trace)
    print("\n[tools] " + tools_line + "\n\n" + answer + "\n" + "-" * 80)
    return tools_line, answer


if __name__ == "__main__":
    if "--samples" in sys.argv:
        md = [f"# Sample answers (generated {date.today()}, model {agent.os.getenv('LLM_MODEL')})\n",
              "Produced by `python cli.py --samples --save docs/SAMPLES.md`. Numbers come from tools; "
              "the LLM wrote the text.\n"]
        runs = [[q] for q in SAMPLES] + [list(FOLLOW_UP)]
        for conv in runs:
            history = []
            for q in conv:
                print("\n>>> " + q)
                tools_line, answer = turn(history, q)
                md += [f"\n---\n\n## Q: {q}\n", f"*Tools called:* `{tools_line}`\n", answer + "\n"]
        if "--save" in sys.argv:
            path = sys.argv[sys.argv.index("--save") + 1]
            with open(path, "w") as f:
                f.write("\n".join(md))
            print(f"\nSaved to {path}")
        sys.exit()

    history = []
    while True:
        q = input("\nYou: ").strip()
        if q.lower() in {"exit", "quit"}:
            break
        if q:
            turn(history, q)
