"""Read the task description of 17139 and 18211."""
import json
for tid in ("sympy__sympy-17139", "sympy__sympy-18211", "sympy__sympy-15599", "sympy__sympy-17630", "sympy__sympy-21612"):
    d = json.load(open(f"trajectories/{tid}__seed__t0.json"))
    steps = d["rollout"]["trace"]["steps"]
    for s in steps:
        if s.get("source") == "user":
            print(f"\n######## {tid}")
            print((s.get("message") or "")[:900])
            break
