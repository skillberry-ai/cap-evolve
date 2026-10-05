import json, os, sys

FAIL = ["astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
        "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
        "django__django-16032","django__django-16667","pydata__xarray-6992","pylint-dev__pylint-4661",
        "pylint-dev__pylint-4970","pytest-dev__pytest-10356","pytest-dev__pytest-5787",
        "sympy__sympy-15599","sympy__sympy-17630","sympy__sympy-21612"]

for task in FAIL:
    fn = f'trajectories/{task}__cand_0002__t0.json'
    d = json.load(open(fn))
    meta = (d['rollout'].get('metadata')) or {}
    vs = meta.get('verifier_stdout', '') or ''
    # find the tail: the verdict portion
    tail = vs[-1500:]
    print(f"########## {task} ##########")
    print(tail)
    print()
