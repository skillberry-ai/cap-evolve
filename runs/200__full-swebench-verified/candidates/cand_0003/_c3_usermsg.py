import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# How do tests actually run in this environment? Look for how the VERIFIER invokes
# tests for django tasks (./tests/runtests.py ...) and what the agent's env is.
# Check the user message / system template of a django task + a sphinx task.
for task in ["django__django-12039", "sphinx-doc__sphinx-9258"]:
    d = load(task)
    out = ((d.get("rollout") or {}).get("output")) or {}
    steps = out.get("steps") or []
    u = [s["message"] for s in steps if s.get("source") == "user"][0]
    print("=" * 110)
    print(task)
    print(u[:6000])
