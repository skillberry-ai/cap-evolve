import json, sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
steps = d["rollout"]["trace"]["steps"]
print(f"n_steps={len(steps)}")
s0 = steps[0]
print(f"step keys: {list(s0.keys())}")
print(json.dumps(s0, indent=1)[:1500])
