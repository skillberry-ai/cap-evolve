import json, os, re

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

# For the failing tasks, did the agent try `pip install pytest`? What happened?
FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667","pydata__xarray-6992","pylint-dev__pylint-4661",
    "pylint-dev__pylint-4970","pytest-dev__pytest-10356","pytest-dev__pytest-5787",
    "sympy__sympy-15599","sympy__sympy-17630","sympy__sympy-21612",
]
for task in FAILING:
    d = load(task)
    out = ((d.get("rollout") or {}).get("output")) or {}
    steps = out.get("steps") or []
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            if "pip install" in c:
                print(f"{task:42s} step {i}: {c[:150]}")
                o = (obs or "")
                print("      rc=", rc, "|", " / ".join(o.splitlines()[:3])[:200])
