import json, os

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# Check the verifier's model-patch extraction: does verifier_stdout contain the model patch?
# Also check whether the agent's committed changes get into the final patch (git diff HEAD vs base).
d = load("django__django-16667")
meta = d["rollout"].get("metadata") or {}
print("metadata keys:", list(meta.keys()))
for k, v in meta.items():
    if isinstance(v, str):
        print(f"--- {k} (len {len(v)}) ---")
        print(v[:400])
    else:
        print(f"--- {k} ---", json.dumps(v)[:400])
