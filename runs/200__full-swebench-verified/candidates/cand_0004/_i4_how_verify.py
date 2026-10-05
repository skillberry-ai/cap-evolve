import json, os
TRAJ = "trajectories"
def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# See the FULL verifier stdout — how does the harness construct the model patch from the agent's work?
for t in ["django__django-16667", "django__django-16032"]:
    d = load(t)
    vs = ((d.get("rollout") or {}).get("metadata") or {}).get("verifier_stdout", "")
    print("="*90)
    print(t)
    print(vs[:1200])
