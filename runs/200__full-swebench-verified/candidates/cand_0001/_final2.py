import json, os, sys

TRAJ = "trajectories"

data = json.load(open(os.path.join(TRAJ, "django__django-10554__seed__t0.json")))
r = data["rollout"]
out = r.get("output")
# find message content in the output dict
def walk(o, depth=0):
    if depth > 4:
        return
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("messages", "final_output", "message", "content", "history"):
                print("KEY:", k, "type:", type(v))
                print(json.dumps(v)[:2000])
                print()
            else:
                walk(v, depth+1)
walk(out)
