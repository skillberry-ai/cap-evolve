import json, os
TRAJ = "trajectories"
def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# What does the verifier do BEFORE running the tests? Does it checkout tests and apply a test patch?
d = load("django__django-16667")
vs = ((d.get("rollout") or {}).get("metadata") or {}).get("verifier_stdout", "")
print(vs[:2000])
