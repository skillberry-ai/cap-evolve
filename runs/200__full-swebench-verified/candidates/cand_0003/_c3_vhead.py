import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

def obs_of(s):
    if not s.get("observation"):
        return "", None
    try:
        j = json.loads(s["observation"]["results"][0]["content"])
        return j.get("output", "") or "", j.get("returncode")
    except Exception:
        return "", None

# What does the verifier do for django tasks? The verifier stdout for django-12039 (PASSING):
# Check the beginning of verifier stdout to see the exact harness commands.
for task in ["django__django-12039", "sympy__sympy-13480", "sphinx-doc__sphinx-9258"]:
    d = load(task)
    meta = ((d.get("rollout") or {}).get("metadata")) or {}
    vs = meta.get("verifier_stdout", "") or ""
    print("=" * 110)
    print(task, "reward", d["score"]["reward"])
    print("---- HEAD 2500 ----")
    print(vs[:2500])
