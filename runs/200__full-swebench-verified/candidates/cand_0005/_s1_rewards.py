import json, os, sys

TRAJ = 'trajectories'
failing = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
    # also partial/other tasks present in trajectories dir
    "pydata__xarray-6461", "pydata__xarray-6992", "pylint-dev__pylint-4661",
    "pylint-dev__pylint-4970", "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sympy__sympy-15599", "sympy__sympy-17630", "sympy__sympy-21612",
    "sympy__sympy-24213", "django__django-13569", "django__django-13809",
    "django__django-15280", "django__django-15741", "django__django-16485",
    "sphinx-doc__sphinx-8638", "sphinx-doc__sphinx-9367",
]
rows = []
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith('.json'):
        continue
    task = fn.replace('__cand_0002__t0.json', '')
    d = json.load(open(os.path.join(TRAJ, fn)))
    sc = d.get('score') or {}
    ro = d.get('rollout') or {}
    err = ro.get('error')
    steps = ((ro.get('trace') or {}).get('steps')) or []
    # also ATIF steps in output
    out = ro.get('output') or {}
    osteps = out.get('steps') or []
    fm = out.get('final_metrics') or {}
    rows.append((task, sc.get('reward'), len(osteps) or len(steps), str(err)[:60], fm.get('total_cost_usd')))

print(f"{'task':46s} {'reward':>7s} {'steps':>5s} {'cost':>8s}  err")
for r in sorted(rows, key=lambda x: (x[1] if x[1] is not None else -1)):
    print(f"{r[0]:46s} {str(r[1]):>7s} {r[2]:>5d} {str(r[4])[:8]:>8s}  {r[3]}")
