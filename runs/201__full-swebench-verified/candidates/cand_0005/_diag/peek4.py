import json, os, sys

TR = "trajectories"

def load(name):
    return json.load(open(os.path.join(TR, name)))

d = load("django__django-10554__seed__t0.json")
steps = d["rollout"]["output"]["steps"]
print("n steps:", len(steps))
s0 = steps[0]
print(json.dumps(s0, indent=1)[:2500])
