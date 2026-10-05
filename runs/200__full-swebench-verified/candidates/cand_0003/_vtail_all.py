import json, os, sys

TRAJ = "trajectories"

FAILING = [
    "django__django-10554","django__django-11555","django__django-12325","django__django-13121",
    "django__django-13401","django__django-14007","django__django-14376","django__django-15629",
    "django__django-15930","django__django-16032","django__django-16667","matplotlib__matplotlib-22871",
    "pydata__xarray-6992","pylint-dev__pylint-4661","pylint-dev__pylint-4970","pytest-dev__pytest-10356",
    "pytest-dev__pytest-5787","sphinx-doc__sphinx-9258","sympy__sympy-15599","sympy__sympy-17139",
    "sympy__sympy-17630","sympy__sympy-18211","sympy__sympy-21612",
]

for t in FAILING:
    try:
        d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
    except FileNotFoundError:
        continue
    md = d["rollout"].get("metadata") or {}
    vs = md.get("verifier_stdout", "") or ""
    lines = [l for l in vs.splitlines()]
    # print last 45 lines before "SWEBench results starts here"
    idx = None
    for i, ln in enumerate(lines):
        if "SWEBench results starts here" in ln:
            idx = i
            break
    if idx is None:
        print(f"### {t}: no marker; tail:")
        print("\n".join(lines[-15:]))
        print()
        continue
    print(f"### {t}")
    print("\n".join(lines[max(0, idx-30):idx]))
    print()
