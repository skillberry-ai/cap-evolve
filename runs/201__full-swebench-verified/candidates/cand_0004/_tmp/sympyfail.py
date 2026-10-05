"""Check sympy verifier outputs in detail — which test failed."""
import json
import glob

for tid in ["sympy__sympy-15599", "sympy__sympy-17139", "sympy__sympy-18211",
            "sympy__sympy-21612", "sympy__sympy-17630", "sphinx-doc__sphinx-9258",
            "django__django-10554"]:
    f = f"trajectories/{tid}__seed__t0.json"
    d = json.load(open(f))
    md = d["rollout"].get("metadata") or {}
    so = md.get("verifier_stdout") or ""
    print("=" * 100)
    print("##", tid)
    # sympy bin/test prints 'F' markers and a list of failed tests at the bottom
    lines = so.splitlines()
    # print last 60 lines before 'SWEBench results'
    idx = so.find("SWEBench results")
    head = so[:idx if idx > 0 else len(so)]
    print(head[-2500:])
