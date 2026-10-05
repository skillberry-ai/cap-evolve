import json, os, re

TRAJ = 'trajectories'
FAIL = ["astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
        "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
        "django__django-16032","django__django-16667","pydata__xarray-6992","pylint-dev__pylint-4661",
        "pylint-dev__pylint-4970","pytest-dev__pytest-10356","pytest-dev__pytest-5787",
        "sphinx-doc__sphinx-9258","sympy__sympy-15599","sympy__sympy-17139","sympy__sympy-17630",
        "sympy__sympy-18211","sympy__sympy-21612"]
PASS = ["django__django-12039","django__django-12276","django__django-13121","django__django-13401",
        "django__django-13410","django__django-13569","django__django-14580","django__django-15103",
        "django__django-15380","django__django-15851","django__django-15863","django__django-15930",
        "matplotlib__matplotlib-22871","matplotlib__matplotlib-24637","scikit-learn__scikit-learn-25232",
        "sphinx-doc__sphinx-7910","sphinx-doc__sphinx-8035","sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595",
        "sympy__sympy-12096","sympy__sympy-13480","sympy__sympy-24213"]

rows = []
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith('.json'):
        continue
    task = fn.split('__cand_0002__')[0]
    d = json.load(open(os.path.join(TRAJ, fn)))
    reward = (d.get('score') or {}).get('reward')
    rows.append((task, reward, fn))

print(f"{'task':45s} {'reward':>6s}")
for t, r, fn in sorted(rows, key=lambda x: (x[1] or 0)):
    print(f"{t:45s} {r}")
