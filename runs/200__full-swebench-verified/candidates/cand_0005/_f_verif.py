import json, os, re
TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667","pylint-dev__pylint-4661","pylint-dev__pylint-4970",
    "pytest-dev__pytest-10356","pytest-dev__pytest-5787","sphinx-doc__sphinx-9258","sympy__sympy-15599",
    "sympy__sympy-17630","sympy__sympy-21612","pydata__xarray-6992","matplotlib__matplotlib-22871",
]
import sys
for t in (sys.argv[1:] or FAILING):
    d = load(t)
    if d is None:
        print("MISSING", t); continue
    vs = (d["rollout"].get("metadata") or {}).get("verifier_stdout", "") or ""
    print("="*100)
    print("TASK:", t, "reward:", (d.get("score") or {}).get("reward"))
    print(vs[:4000])
