import json, os, sys

TRAJ = "trajectories"

def check_output_diff(task):
    """Check: does the task produce a final message containing a git diff? Does the eval compute a patch from the working tree?"""
    data = json.load(open(os.path.join(TRAJ, f"{task}__seed__t0.json")))
    out = data["rollout"]["output"]
    steps = out.get("steps") or []
    msgs = [s.get("message") or "" for s in steps if s.get("source") == "agent"]
    full = "\n".join(msgs)
    has_diff = "diff --git" in full
    n_msgs_with_diff = sum(1 for m in msgs if "diff --git" in m)
    return has_diff, n_msgs_with_diff, len(msgs)

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

for t in FAILING + PASSING:
    has_diff, n, m = check_output_diff(t)
    tag = "FAIL" if t in FAILING else "PASS"
    print(f"{t:<38} {tag} has_diff_in_final_msgs={has_diff} msgs_with_diff={n}/{m}")
