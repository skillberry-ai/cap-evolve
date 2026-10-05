import json, os, sys

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

FAILING = ["astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
"django__django-12708","django__django-14007","django__django-14376","django__django-15629","django__django-16032",
"django__django-16667","pydata__xarray-6461","pydata__xarray-6992","pylint-dev__pylint-4661","pylint-dev__pylint-4970",
"pytest-dev__pytest-10356","pytest-dev__pytest-5787","sympy__sympy-15599","sympy__sympy-17630","sympy__sympy-21612","sympy__sympy-24213"]

for task in FAILING:
    d = load(task)
    vs = (d['rollout'].get('metadata') or {}).get('verifier_stdout') or ''
    # Find the SWEBench result marker and what's around it
    idx = vs.find('SWEBench results')
    if idx >= 0:
        print(f"### {task}")
        print(vs[max(0,idx-2600):idx+200])
        print("="*100)
