import json
for t in ["django__django-15930", "sphinx-doc__sphinx-9258", "sympy__sympy-21612", "django__django-12039"]:
    d = json.load(open(f"trajectories/{t}__seed__t0.json"))
    vs = d["rollout"]["metadata"].get("verifier_stdout", "")
    hits = [l for l in vs.splitlines() if "miniconda" in l or "testbed" in l][:2]
    print(t, "->", hits if hits else "no env-path evidence in verifier stdout")
