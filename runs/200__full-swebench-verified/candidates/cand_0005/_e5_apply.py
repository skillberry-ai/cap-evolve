import json, os, re

TRAJ = "trajectories"

FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667","pylint-dev__pylint-4661","pylint-dev__pylint-4970",
    "pytest-dev__pytest-10356","pytest-dev__pytest-5787","sympy__sympy-15599",
    "sympy__sympy-17630","sympy__sympy-21612","pydata__xarray-6992",
]
PASSING = [
    "django__django-12039","django__django-12276","django__django-13121","django__django-13401",
    "django__django-13410","django__django-13569","django__django-14580","django__django-15103",
    "django__django-15380","django__django-15851","django__django-15863","django__django-15930",
    "matplotlib__matplotlib-24637","scikit-learn__scikit-learn-25232","sphinx-doc__sphinx-7910",
    "sphinx-doc__sphinx-8035","sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595","sympy__sympy-12096",
    "sympy__sympy-13480","sympy__sympy-17139","sympy__sympy-18211",
]

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

def obs_of(s):
    obs, rc = "", None
    if s.get("observation"):
        try:
            c = s["observation"]["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output", "") or ""
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc

# Count: git apply failures and how the agent recovered; use of python - <<PY for edits;
# and whether the final commit exists and diff was produced.
def summarize(task):
    d = load(task)
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    n_apply_fail = 0
    n_apply_try = 0
    recovered = False  # used python Path write after failed apply
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            if c.startswith(("git apply", "applypatch")):
                n_apply_try += 1
                if rc not in (0, None):
                    n_apply_fail += 1
                    # check next commands for python - << recovery
    return n_apply_try, n_apply_fail

rows_f = [(t,) + summarize(t) for t in FAILING]
rows_p = [(t,) + summarize(t) for t in PASSING]
print("FAILING:")
for r in rows_f:
    print(f"  {r[0]:42s} apply_try={r[1]} apply_fail={r[2]}")
print("PASSING:")
for r in rows_p:
    print(f"  {r[0]:42s} apply_try={r[1]} apply_fail={r[2]}")
