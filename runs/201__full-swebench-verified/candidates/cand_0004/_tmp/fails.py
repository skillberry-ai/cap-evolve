import json, os, glob

TRAJ = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004/trajectories"

# For failing tasks, print the verifier stdout tail (the actual test results / FAIL lines)
FAILING = [
    "django__django-10554", "django__django-12325", "django__django-14376",
    "django__django-15629", "django__django-16667",
    "matplotlib__matplotlib-22871", "pydata__xarray-6461", "pydata__xarray-6992",
    "pylint-dev__pylint-4661", "pylint-dev__pylint-4970",
    "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sphinx-doc__sphinx-9258", "sympy__sympy-15599", "sympy__sympy-17139",
    "sympy__sympy-17630", "sympy__sympy-18211", "sympy__sympy-21612",
]

for f in sorted(glob.glob(os.path.join(TRAJ, "*.json"))):
    data = json.load(open(f))
    tid = data["score"]["task_id"]
    if tid not in FAILING:
        continue
    md = data["rollout"].get("metadata") or {}
    so = md.get("verifier_stdout") or ""
    print("=" * 110)
    print(f"## {tid}  reward={data['score']['reward']}")
    print("=" * 110)
    # find FAIL lines / summary
    lines = so.splitlines()
    fails = [l for l in lines if ("FAIL" in l or "ERROR" in l or "failed" in l.lower())]
    print("--- FAIL/ERROR lines (up to 40) ---")
    for l in fails[:40]:
        print(l[:300])
    print("--- tail 30 lines ---")
    for l in lines[-30:]:
        print(l[:300])
