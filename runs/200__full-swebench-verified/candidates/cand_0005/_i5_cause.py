import json, os, sys, collections

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

def obs_of(s):
    if not s.get("observation"):
        return "", None
    try:
        j = json.loads(s["observation"]["results"][0]["content"])
        return j.get("output", "") or "", j.get("returncode")
    except Exception:
        return "", None

def cmd_of(s):
    for tc in (s.get("tool_calls") or []):
        return (tc.get("arguments") or {}).get("command", "")
    return ""

# Categorize each failing task by ROOT CAUSE of the verifier failure:
# A) agent's fix is wrong / incomplete (test assertion fails) — logic
# B) agent broke the environment (stray files, uninstalled deps) — env damage
# C) agent's fix caused an exception elsewhere — regression
# Look at the verifier output: which test failed and why.
tasks = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555", "django__django-12325",
    "django__django-12708", "django__django-14007", "django__django-14376", "django__django-15629",
    "django__django-16032", "django__django-16667", "pydata__xarray-6461", "pydata__xarray-6992",
    "pylint-dev__pylint-4661", "pylint-dev__pylint-4970", "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sympy__sympy-15599", "sympy__sympy-17630", "sympy__sympy-21612", "sympy__sympy-24213",
]
for task in tasks:
    d = load(task)
    md = (d.get("rollout") or {}).get("metadata") or {}
    vs = md.get("verifier_stdout", "") or ""
    # The failing test name is usually in 'FAILED ...' or 'FAIL: ...'
    lines = vs.splitlines()
    fails = [l for l in lines if l.strip().startswith(("FAILED", "FAIL:", "ERROR:", "ERROR ", "F ")) or "AssertionError" in l]
    print("=" * 90)
    print("###", task)
    for l in fails[:8]:
        print("  ", l[:170])
