import json, os, sys

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# The stdout is truncated to 5000. Check verifier_stderr too, and the whole output.steps for
# a final agent message (the model patch may be extracted from the final message).
for task in ["django__django-15863", "astropy__astropy-13453"]:
    d = load(task)
    md = (d.get("rollout") or {}).get("metadata") or {}
    ve = md.get("verifier_stderr", "") or ""
    print("=" * 80)
    print("###", task, "stderr len", len(ve))
    print(ve[:1500])
