import json, os, sys

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

# passing tasks: gather their final steps to see how the successful ones verify.
targets = [
    "django__django-12039", "django__django-12276", "django__django-13121", "django__django-13401",
    "django__django-13410", "django__django-13569", "django__django-14580", "django__django-15103",
    "django__django-15380", "django__django-15851", "django__django-15863", "django__django-15930",
    "matplotlib__matplotlib-22871", "matplotlib__matplotlib-24637", "scikit-learn__scikit-learn-25232",
    "sphinx-doc__sphinx-7910", "sphinx-doc__sphinx-8035", "sphinx-doc__sphinx-8475",
    "sphinx-doc__sphinx-8595", "sphinx-doc__sphinx-9258", "sympy__sympy-12096",
    "sympy__sympy-13480", "sympy__sympy-17139", "sympy__sympy-18211",
]

# For each: what test commands did they run? Did they run the repo's runner (runtests.py / tests/ / python -m pytest / tox)?
import collections
stats = collections.Counter()
per_task = {}
for task in targets:
    d = load(task)
    steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
    cmds = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        c = cmd_of(s)
        obs, rc = obs_of(s)
        cmds.append((c, rc))
    # test-ish commands
    test_cmds = [c for c, rc in cmds if any(m in c for m in ("pytest", "py.test", "runtests.py", "bin/test", "./tests", "tox"))]
    ran_tests = [c for c in test_cmds if "not found" not in (obs_of  if False else "")]
    # successful test runs: rc==0
    ok_runs = 0
    for s in steps:
        if s.get("source") != "agent":
            continue
        c = cmd_of(s)
        obs, rc = obs_of(s)
        if any(m in c for m in ("pytest", "py.test", "runtests.py", "bin/test", "tox", "./tests")) and rc == 0:
            ok_runs += 1
    per_task[task] = (len(test_cmds), ok_runs)

for t, (n, ok) in per_task.items():
    print(f"{t:44s} test_cmds={n:2d} ok_runs={ok:2d}")
