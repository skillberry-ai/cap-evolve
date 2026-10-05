import json, os

# For each failing trajectory: print the final submission output and key info
fails = [
    "django__django-10554", "django__django-12325", "django__django-14376",
    "django__django-15629", "django__django-16667", "matplotlib__matplotlib-22871",
    "pydata__xarray-6461", "pydata__xarray-6992", "pylint-dev__pylint-4661",
    "pylint-dev__pylint-4970", "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sphinx-doc__sphinx-9258", "sympy__sympy-15599", "sympy__sympy-17139",
    "sympy__sympy-17630", "sympy__sympy-18211", "sympy__sympy-21612",
]

for t in fails:
    p = f"trajectories/{t}__seed__t0.json"
    with open(p) as f:
        d = json.load(f)
    md = d["rollout"].get("metadata") or {}
    vs = (md.get("verifier_stdout") or "")[:800]
    print(f"===== {t} =====")
    print(vs)
    print()
