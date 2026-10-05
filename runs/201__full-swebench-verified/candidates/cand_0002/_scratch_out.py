"""Dump rollout.output (may be dict) (optimizer scratch)."""
import json
import sys

for path in sys.argv[1:]:
    with open(path) as f:
        d = json.load(f)
    score = d["score"]
    ro = d["rollout"]
    out = ro.get("output")
    print(f"\n######## {score['task_id']}  reward={score['reward']}  output type={type(out).__name__}")
    if isinstance(out, dict):
        print("output keys:", list(out.keys()))
        s = json.dumps(out)
        print(s[:2500])
    else:
        print((out or "")[:2500])
