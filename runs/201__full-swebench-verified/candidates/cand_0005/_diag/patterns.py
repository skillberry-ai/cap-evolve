import json, os, sys

TR = "trajectories"

FAILING = [
    "django__django-10554", "django__django-12325", "django__django-14376",
    "django__django-15629", "django__django-16667", "matplotlib__matplotlib-22871",
    "pydata__xarray-6461", "pydata__xarray-6992", "pylint-dev__pylint-4661",
    "pylint-dev__pylint-4970", "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sphinx-doc__sphinx-9258", "sympy__sympy-15599", "sympy__sympy-17139",
    "sympy__sympy-17630", "sympy__sympy-18211", "sympy__sympy-21612",
]
# more failing than the prompt list — prompt lists 18 ALWAYS-failing; trajectories show these too.
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

def load(task):
    return json.load(open(os.path.join(TR, task + "__seed__t0.json")))

def cmds(task):
    d = load(task)
    out = []
    for s in d["rollout"]["output"]["steps"]:
        if s.get("source") != "agent":
            continue
        for i, tc in enumerate(s.get("tool_calls") or []):
            out.append((s.get("step_id"), (tc.get("arguments") or {}).get("command", "")))
    return out

# Heuristics to detect failure patterns
patterns = {
    "ModuleNotFoundError": lambda t: t,
    "ModuleNotFound": lambda t: t,
    "pytest not found": lambda t: t,
}

print("FAILING tasks — look for verification issues")
for t in FAILING:
    d = load(t)
    text = json.dumps(d["rollout"]["output"]["steps"])
    markers = []
    if "ModuleNotFoundError" in text:
        # find which module
        mods = set()
        import re
        for m in re.findall(r"No module named '([^']+)'", text):
            mods.add(m)
        markers.append("ModuleNotFoundError:" + ",".join(sorted(mods)))
    if "pytest: not found" in text:
        markers.append("pytest-not-found")
    if "verify-fix" in text:
        markers.append("used-verify-fix")
    # did they run any test that PASSED (rc 0)?
    print(f"{t:40s} {' | '.join(markers) if markers else '(clean)'}")
