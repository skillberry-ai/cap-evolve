import json, os
TRAJ = "trajectories"
def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# The verifier stdout seems truncated at 5000 chars from the START (vlen=5000).
# For 16667 the stdout begins mid-test-file, meaning the beginning was cut. Let's check
# a PASSING task's verifier stdout to see the format from the beginning.
d = load("django__django-12039")
vs = ((d.get("rollout") or {}).get("metadata") or {}).get("verifier_stdout", "")
print("12039 len:", len(vs))
print(vs[:2500])
