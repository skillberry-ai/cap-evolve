import json, os, re

TR = "trajectories"
PASSING = [
    "astropy__astropy-13453", "django__django-11555", "django__django-12039",
    "django__django-12276", "django__django-12708", "django__django-13121",
    "django__django-13401", "django__django-13410", "django__django-13569",
    "django__django-13809", "django__django-14007", "django__django-14580",
    "django__django-15103", "django__django-15380", "django__django-15851",
    "django__django-15863", "django__django-15930", "django__django-16032",
    "django__django-16485", "matplotlib__matplotlib-24637",
    "scikit-learn__scikit-learn-25232", "sphinx-doc__sphinx-7910",
    "sphinx-doc__sphinx-8035", "sphinx-doc__sphinx-8475", "sphinx-doc__sphinx-8595",
    "sphinx-doc__sphinx-9367", "sympy__sympy-12096", "sympy__sympy-13480",
    "sympy__sympy-24213",
]

for t in PASSING:
    d = json.load(open(os.path.join(TR, t + "__seed__t0.json")))
    text = json.dumps(d["rollout"]["output"]["steps"])
    markers = []
    if "ModuleNotFoundError" in text:
        mods = set(re.findall(r"No module named '([^']+)'", text))
        markers.append("MNFE:" + ",".join(sorted(mods)))
    if "pytest: not found" in text:
        markers.append("pytest-not-found")
    if "verify-fix" in text:
        markers.append("used-verify-fix")
    print(f"{t:40s} {' | '.join(markers) if markers else '(clean)'}")
