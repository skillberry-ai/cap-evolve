import json, os, sys

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

d = load("sympy__sympy-24213")
md = (d.get("rollout") or {}).get("metadata") or {}
vs = md.get("verifier_stdout", "") or ""
i = vs.find("bin/test")
print(vs[i-600:i+400])
