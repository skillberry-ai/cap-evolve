import json, os, sys

TR = "trajectories"

d = json.load(open(os.path.join(TR, "django__django-10554__seed__t0.json")))
roll = d["rollout"]
for k, v in roll.items():
    if isinstance(v, (list, dict, str)):
        print("rollout.", k, type(v).__name__, len(v))
    else:
        print("rollout.", k, repr(v)[:120])
print()
sc = d["score"]
for k, v in sc.items():
    print("score.", k, repr(v)[:300])
