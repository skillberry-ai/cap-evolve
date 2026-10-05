import json, os, sys

TR = "trajectories"

def load(name):
    return json.load(open(os.path.join(TR, name)))

d = load("django__django-10554__seed__t0.json")
steps = d["rollout"]["output"]["steps"]
for i, s in enumerate(steps[2:10], start=2):
    keys = list(s.keys())
    print(f"--- idx {i} keys={keys}")
    print(json.dumps(s, indent=1)[:1500])
    print()
