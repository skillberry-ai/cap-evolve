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

FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555", "django__django-12325",
    "django__django-12708", "django__django-14007", "django__django-14376", "django__django-15629",
    "django__django-16032", "django__django-16667", "pydata__xarray-6461", "pydata__xarray-6992",
    "pylint-dev__pylint-4661", "pylint-dev__pylint-4970", "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sympy__sympy-15599", "sympy__sympy-17630", "sympy__sympy-21612", "sympy__sympy-24213",
]

# 1. how many failing tasks did the agent COMMIT its changes (git add/commit)?
# 2. how many verified with any green run?
# 3. what is the failure verdict per verifier (specific test failing)?
commits = {}
for task in FAILING:
    d = load(task)
    steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
    n_commit = 0
    n_gitapply = 0
    for s in steps:
        if s.get("source") != "agent":
            continue
        c = cmd_of(s)
        if "git add" in c and "git commit" in c:
            n_commit += 1
        if c.startswith("git apply") or "git apply -" in c:
            n_gitapply += 1
    commits[task] = (n_commit, n_gitapply)

print(f"{'task':44s} {'commits':>7s} {'gitapply':>8s}")
for t, (nc, ng) in commits.items():
    print(f"{t:44s} {nc:7d} {ng:8d}")
