"""Full failure diagnosis: for each failing task, extract
- the commands the agent ran to TEST (and their outcomes)
- the agent's final patch (from git diff in trace)
- the verifier's failing tests
"""
import json
import os
import glob
import re

TRAJ = "trajectories"

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


def get_cmds(step):
    out = []
    for tc in (step.get("tool_calls") or []):
        c = (tc.get("arguments") or {}).get("command", "")
        if c:
            out.append(c)
    return out


def get_obs(step):
    obs = step.get("observation") or {}
    txt = ""
    try:
        for r in (obs.get("results") or []):
            c = r.get("content", "")
            try:
                j = json.loads(c)
                txt = f"rc={j.get('returncode')} | " + str(j.get("output") or j.get("output_head") or "")[:800]
            except Exception:
                txt = c[:800]
    except Exception:
        pass
    return txt


which = sys_task = None
import sys

for f in sorted(glob.glob(os.path.join(TRAJ, "*.json"))):
    data = json.load(open(f))
    tid = data["score"]["task_id"]
    if tid not in FAILING:
        continue
    steps = (data["rollout"].get("output") or {}).get("steps", [])
    md = data["rollout"].get("metadata") or {}
    so = md.get("verifier_stdout") or ""
    print("=" * 110)
    print("##", tid)
    # testing-related commands
    print("--- test/verify commands:")
    for s in steps:
        for c in get_cmds(s):
            if re.search(r"pytest|runtests|bin/test|verify-fix|python -c|python -m|tox|nosetests|python3 ", c):
                obs = get_obs(s)
                print("  CMD:", c[:220].replace("\n", " ⏎ "))
                print("    ->", obs[:300].replace("\n", " | "))
    # final diff
    print("--- last git diff seen:")
    last_diff = ""
    for s in steps:
        for c in get_cmds(s):
            if "git diff" in c or "git --no-pager diff" in c:
                last_diff = get_obs(s)
    print(last_diff[:1500])
    # verifier failing lines
    print("--- verifier FAILED/ERROR lines:")
    for ln in so.splitlines():
        if ln.startswith("FAILED") or ln.startswith("ERROR") or "FAILED (" in ln or "failed" in ln.lower() and "passed" in ln.lower():
            print("   ", ln[:220])
