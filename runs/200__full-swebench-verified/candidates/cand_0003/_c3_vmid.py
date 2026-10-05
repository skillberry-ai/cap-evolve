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

# For sympy-15599/17630/21612 and django-10554/14007, the failing-test info must be in
# the truncated middle of the verifier output. Look at what we have: they show
# 'SWEBench' only because the results section says FAILED. Let me look at their FULL
# verifier stdout more carefully (the last 5000 chars are stored).
for task in ["sympy__sympy-15599", "sympy__sympy-17630", "sympy__sympy-21612",
             "django__django-10554", "django__django-14007", "pytest-dev__pytest-5787",
             "pydata__xarray-6992", "django__django-16667"]:
    d = load(task)
    meta = ((d.get("rollout") or {}).get("metadata")) or {}
    vs = meta.get("verifier_stdout", "") or ""
    print("=" * 100)
    print(task, "vs len:", len(vs))
    # show the middle where failures usually print
    print(vs[1500:4500])
