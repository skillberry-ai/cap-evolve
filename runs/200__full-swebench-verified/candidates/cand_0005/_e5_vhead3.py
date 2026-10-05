import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

for task in ["sympy__sympy-17630","sympy__sympy-21612","django__django-12325"]:
    d = load(task)
    vs = (d["rollout"].get("metadata") or {}).get("verifier_stdout", "") or ""
    print(f"== {task}")
    print(vs[:2500])
    print("----")
