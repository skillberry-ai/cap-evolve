import json
d = json.load(open("trajectories/sympy__sympy-21612__seed__t0.json"))
steps = d["rollout"]["trace"]["steps"]
print("n steps:", len(steps))
print("sample step_ids:", [s.get("step_id") for s in steps[:25]])
