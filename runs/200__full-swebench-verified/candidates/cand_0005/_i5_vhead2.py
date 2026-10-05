import json, os, sys

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

d = load("django__django-15863")
md = (d.get("rollout") or {}).get("metadata") or {}
vs = md.get("verifier_stdout", "") or ""
# find the actual test invocation
idx = vs.find("tee /tmp")
print(vs[idx:idx+2500])
