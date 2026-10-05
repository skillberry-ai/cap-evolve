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
    d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
    vs = (d['rollout'].get('metadata') or {}).get('verifier_stdout', '') or ''
    # find the FAIL/FAIL_TO_PASS portion: look for lines with 'FAILED' 'PASS' 'FAIL' near test names
    lines = vs.splitlines()
    keep = []
    for i, ln in enumerate(lines):
        low = ln.lower()
        if ('failed' in low and ('test' in low or 'error' in low)) or 'traceback' in low or 'passed' in low or low.startswith('fail') or 'swebench results' in low:
            keep.append(ln[:200])
    print(f"===== {t} =====")
    print("\n".join(keep[-25:]))
    print()
