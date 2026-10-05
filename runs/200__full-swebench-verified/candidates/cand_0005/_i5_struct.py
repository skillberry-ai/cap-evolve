import json, os, sys

TRAJ = "trajectories"

def load(task_prefix):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task_prefix + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

d = load("django__django-10554")
print("top keys:", list(d.keys()))
print("score:", d.get("score"))
r = d.get("rollout") or {}
print("rollout keys:", list(r.keys()))
tr = r.get("trace") or {}
print("trace keys:", list(tr.keys()))
steps = tr.get("steps") or []
print("n steps:", len(steps))
if steps:
    print("step keys:", list(steps[0].keys()))
    print("first step:", json.dumps(steps[0])[:600])
out = r.get("output") or {}
print("output keys:", list(out.keys()))
