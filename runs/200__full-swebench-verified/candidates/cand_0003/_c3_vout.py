import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

for task in ["django__django-14007", "django__django-10554", "pylint-dev__pylint-4661", "django__django-12039"]:
    d = load(task)
    meta = ((d.get("rollout") or {}).get("metadata")) or {}
    vs = meta.get("verifier_stdout", "") or ""
    print("=" * 100)
    print(task, "reward", d["score"]["reward"])
    print(vs[:3500])
