import json, os, sys

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# The final agent message for pytest-5787 said "I'll display the git diff" — the model patch
# is likely extracted from the container's git state (git diff after agent), not from the message.
# Key question: does COMMITTING hurt? Compare: passing tasks that committed vs failing tasks that committed.
PASSING = [
    "django__django-12039", "django__django-12276", "django__django-13121", "django__django-13401",
    "django__django-13410", "django__django-13569", "django__django-14580", "django__django-15103",
    "django__django-15380", "django__django-15851", "django__django-15863", "django__django-15930",
    "matplotlib__matplotlib-22871", "matplotlib__matplotlib-24637", "scikit-learn__scikit-learn-25232",
    "sphinx-doc__sphinx-7910", "sphinx-doc__sphinx-8035", "sphinx-doc__sphinx-8475",
    "sphinx-doc__sphinx-8595", "sphinx-doc__sphinx-9258", "sympy__sympy-12096",
    "sympy__sympy-13480", "sympy__sympy-17139", "sympy__sympy-18211",
]

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

for label, tasks in (("PASSING", PASSING),):
    n_commit = 0
    for task in tasks:
        d = load(task)
        steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
        has_commit = False
        for s in steps:
            if s.get("source") != "agent":
                continue
            c = cmd_of(s)
            if "git commit" in c:
                has_commit = True
        if has_commit:
            n_commit += 1
    print(f"{label}: {n_commit}/{len(tasks)} tasks committed their work")
