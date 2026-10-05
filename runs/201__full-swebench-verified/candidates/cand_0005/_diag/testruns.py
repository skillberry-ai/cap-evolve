"""For each failing task: what did the agent try to run tests with, and what failed?

Also check: did the agent ever discover /opt/conda envs? Did any task have a
working test run at some point?
"""
import glob
import json
import re

FAIL = [
    "django__django-10554", "django__django-12325", "django__django-14376",
    "django__django-15629", "django__django-16667", "matplotlib__matplotlib-22871",
    "pydata__xarray-6461", "pydata__xarray-6992", "pylint-dev__pylint-4661",
    "pylint-dev__pylint-4970", "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sphinx-doc__sphinx-9258", "sympy__sympy-15599", "sympy__sympy-17139",
    "sympy__sympy-17630", "sympy__sympy-18211", "sympy__sympy-21612",
]

for f in sorted(glob.glob("trajectories/*.json")):
    d = json.load(open(f))
    tid = d["rollout"]["task_id"]
    if tid not in FAIL:
        continue
    steps = d["rollout"]["trace"]["steps"]
    print(f"\n===== {tid} =====")
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in s.get("tool_calls") or []:
            cmd = (tc.get("arguments") or {}).get("command", "")
            # test-running attempts only
            if re.search(r"(pytest|runtests|bin/test|python -m pytest|tox|nosetests|\.py)", cmd) and \
               re.search(r"(test|repro|verify)", cmd):
                obs = ""
                for r in (s.get("observation") or {}).get("results") or []:
                    c = r.get("content", "")
                    try:
                        j = json.loads(c)
                        obs = (j.get("output") or "").strip().replace("\n", " | ")[:220]
                    except Exception:
                        obs = c[:150]
                print(f"  [{s.get('step_id')}] CMD: {cmd[:150]}")
                print(f"        OBS: {obs}")
