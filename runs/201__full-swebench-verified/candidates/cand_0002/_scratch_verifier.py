"""Extract verifier output + final patch state per trajectory (optimizer scratch)."""
import json
import sys

for path in sys.argv[1:]:
    with open(path) as f:
        d = json.load(f)
    score = d["score"]
    md = d.get("metadata") or {}
    vo = md.get("verifier_stdout") or ""
    tid = score["task_id"]
    print(f"\n######## {tid}  reward={score['reward']}")
    print(f"### feedback: {(score.get('feedback') or '')[:400]}")
    if vo:
        # print tail which usually has the test summary
        lines = vo.splitlines()
        head = "\n".join(lines[:6])
        tail = "\n".join(lines[-40:])
        print("### verifier head:")
        print(head)
        print("### verifier tail:")
        print(tail)
    else:
        print("### (no verifier_stdout)")
