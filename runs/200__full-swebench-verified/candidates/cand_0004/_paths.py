import json, os, re, sys

TRAJ = "trajectories"

FAILING = [
    "django__django-10554","django__django-11555","django__django-12325","django__django-13121",
    "django__django-13401","django__django-14007","django__django-14376","django__django-15629",
    "django__django-15930","django__django-16032","django__django-16667","matplotlib__matplotlib-22871",
    "pydata__xarray-6992","pylint-dev__pylint-4661","pylint-dev__pylint-4970","pytest-dev__pytest-10356",
    "pytest-dev__pytest-5787","sphinx-doc__sphinx-9258","sympy__sympy-15599","sympy__sympy-17139",
    "sympy__sympy-17630","sympy__sympy-18211","sympy__sympy-21612",
]
PASSING = [
    "astropy__astropy-13453","django__django-12039","django__django-12276","django__django-12708",
    "django__django-13410","django__django-13569","django__django-13809","django__django-14580",
    "django__django-15103","django__django-15380","django__django-15851","django__django-15863",
    "django__django-16485","matplotlib__matplotlib-24637","pydata__xarray-6461",
    "scikit-learn__scikit-learn-25232","sphinx-doc__sphinx-7910","sphinx-doc__sphinx-8035",
    "sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595","sphinx-doc__sphinx-9367","sympy__sympy-12096",
    "sympy__sympy-13480","sympy__sympy-24213",
]

def summary(task):
    p = os.path.join(TRAJ, f"{task}__seed__t0.json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    md = d["rollout"].get("metadata") or {}
    vs = md.get("verifier_stdout", "") or ""
    upd = re.findall(r"Updated (\d+) paths? from (\w+)", vs)
    n_paths = [int(n) for n, _ in upd]
    return d["score"]["reward"], max(n_paths) if n_paths else 0

print("=== FAILING ===")
for t in FAILING:
    r = summary(t)
    if r: print(f"{t:44s} reward={r[0]} max_paths_updated={r[1]}")
print()
print("=== PASSING ===")
for t in PASSING:
    r = summary(t)
    if r: print(f"{t:44s} reward={r[0]} max_paths_updated={r[1]}")
