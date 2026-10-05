import json, os, sys

TR = "trajectories"
d = json.load(open(os.path.join(TR, "django__django-10554__seed__t0.json")))
roll = d["rollout"]
out = roll["output"]
tr = roll["trace"]
for k, v in out.items():
    print("output.", k, type(v).__name__, len(v) if isinstance(v, (list, dict, str)) else v)
print()
for k, v in tr.items():
    print("trace.", k, type(v).__name__, len(v) if isinstance(v, (list, dict, str)) else v)
print()
print(json.dumps(out, indent=1)[:3000])
