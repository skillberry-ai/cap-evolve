"""Extract verifier FAILED test names per failing task, from verifier_stdout."""
import json
import glob
import re
import os

FAILING = [
    "django__django-10554", "django__django-12325", "django__django-14376",
    "django__django-15629", "django__django-16667",
    "matplotlib__matplotlib-22871", "pydata__xarray-6461", "pydata__xarray-6992",
    "pylint-dev__pylint-4661", "pylint-dev__pylint-4970",
    "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sphinx-doc__sphinx-9258",
    "sympy__sympy-15599", "sympy__sympy-17139", "sympy__sympy-17630",
    "sympy__sympy-18211", "sympy__sympy-21612",
]

for f in sorted(glob.glob("trajectories/*.json")):
    d = json.load(open(f))
    tid = d["score"]["task_id"]
    if tid not in FAILING:
        continue
    md = d["rollout"].get("metadata") or {}
    so = md.get("verifier_stdout") or ""
    # split at the pre-verifier part; the run-tests output usually begins with a banner
    # find FAILED/ERROR lines
    print("==", tid)
    lines = so.splitlines()
    started = False
    for i, ln in enumerate(lines):
        if re.match(r"^(FAILED|ERROR|FAIL:|ERROR:)", ln):
            print("  ", ln[:250])
    # also the tail
    tail = [ln for ln in lines if ("passed" in ln and "failed" in ln) or "FAILED (" in ln]
    for t in tail[-3:]:
        print("  TAIL:", t[:200])
