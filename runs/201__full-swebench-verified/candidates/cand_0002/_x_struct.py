import json, sys, glob

p = sys.argv[1] if len(sys.argv) > 1 else "trajectories/django__django-10554__seed__t0.json"
with open(p) as f:
    d = json.load(f)
print(type(d))
if isinstance(d, dict):
    for k, v in d.items():
        s = json.dumps(v)[:300] if not isinstance(v, str) else v[:300]
        print("==", k, "==")
        print(s)
