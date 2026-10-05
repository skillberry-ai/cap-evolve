import json, os, sys

TRAJ = 'trajectories'
FAILING = ["astropy__astropy-13453","django__django-10554","django__django-11555",
    "django__django-12325","django__django-12708","django__django-14007",
    "django__django-14376","django__django-15629","django__django-16032",
    "django__django-16667","pydata__xarray-6461","pydata__xarray-6992",
    "pylint-dev__pylint-4661","pylint-dev__pylint-4970","pytest-dev__pytest-10356",
    "pytest-dev__pytest-5787","sympy__sympy-15599","sympy__sympy-17630",
    "sympy__sympy-21612","sympy__sympy-24213"]

for t in FAILING:
    fn = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    if not os.path.exists(fn):
        continue
    d = json.load(open(fn))
    md = ((d.get('rollout') or {}).get('metadata')) or {}
    vs = md.get('verifier_stdout') or ''
    # last 40 lines of verifier stdout
    lines = [l for l in vs.splitlines() if l.strip()]
    print(f"########## {t} ##########")
    print('\n'.join(lines[-25:]))
    print()
