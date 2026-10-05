"""Look at sympy-15599's diff more carefully: the task literally provides the exact diff to apply. Compare agent's diff with the gold one."""
import json
d = json.load(open("trajectories/sympy__sympy-15599__seed__t0.json"))
steps = d["rollout"]["trace"]["steps"]
for s in steps:
    if s.get("source") == "user":
        print((s.get("message") or "")[:2500])
        break
