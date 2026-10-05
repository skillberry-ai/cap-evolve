import json, os, sys

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# Find the test command line the verifier uses. Look at verifier_stderr or reward_json for the command.
for task in ["django__django-15863", "sympy__sympy-17630", "pylint-dev__pylint-4970"]:
    d = load(task)
    md = (d.get("rollout") or {}).get("metadata") or {}
    rj = md.get("reward_json") or ""
    print("=" * 80)
    print("###", task)
    print("reward_json (first 1200):", rj[:1200] if isinstance(rj, str) else json.dumps(rj)[:1200])
