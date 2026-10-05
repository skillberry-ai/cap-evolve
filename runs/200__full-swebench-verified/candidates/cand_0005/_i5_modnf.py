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

# Count error signatures across all failing tasks: module-not-found during agent-run verification
modnf = collections.Counter()
pip_install = collections.Counter()
tasks_with_modnf = collections.defaultdict(set)
tasks_with_pip = collections.defaultdict(set)
for task in FAILING:
    d = load(task)
    steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
    for s in steps:
        if s.get("source") != "agent":
            continue
        c = cmd_of(s)
        obs, rc = obs_of(s)
        if "ModuleNotFoundError" in (obs or ""):
            import re
            for m in re.findall(r"No module named '([^']+)'", obs):
                modnf[m] += 1
                tasks_with_modnf[m].add(task)
        if "pip" in c and ("install" in c):
            pip_install[c[:60]] += 1
            tasks_with_pip[c[:60]].add(task)

print("=== ModuleNotFoundError seen by the agent while verifying (module: count, #tasks) ===")
for m, n in modnf.most_common():
    print(f"  {m:25s} count={n:2d} tasks={len(tasks_with_modnf[m])}")
print()
print("=== pip install commands ===")
for c, n in pip_install.most_common():
    print(f"  {n:2d}x {c}   (tasks: {len(tasks_with_pip[c])})")
