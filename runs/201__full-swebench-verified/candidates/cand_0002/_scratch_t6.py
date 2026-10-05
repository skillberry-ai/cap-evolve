import json
d = json.load(open("trajectories/sympy__sympy-21612__seed__t0.json"))
steps = d["rollout"]["trace"]["steps"]
s = steps[18]  # step 19
print("keys:", list(s.keys()))
for k, v in s.items():
    sv = json.dumps(v)
    print(f"{k}: {sv[:300]}")
