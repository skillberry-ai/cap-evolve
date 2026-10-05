import json, os, sys

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# The verifier metadata: which python / runner does the harness use? Show first 3000 chars of verifier_stdout for a passing task
d = load("django__django-15863")
md = (d.get("rollout") or {}).get("metadata") or {}
vs = md.get("verifier_stdout", "") or ""
print(vs[:3500])
