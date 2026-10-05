import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# The verifier output is TRUNCATED at 5000 chars (starts mid-way). Let me check the
# full metadata keys available.
d = load("django__django-12039")
meta = ((d.get("rollout") or {}).get("metadata")) or {}
print("metadata keys:", list(meta.keys()))
for k, v in meta.items():
    if isinstance(v, str):
        print(f"--- {k} (len {len(v)}) ---")
        print(v[:300])
    else:
        print(f"--- {k} ---", json.dumps(v)[:300])
# Also check top-level keys
print("TOP KEYS:", list(d.keys()))
print("rollout keys:", list(d["rollout"].keys()))
out = d["rollout"].get("output") or {}
print("output keys:", list(out.keys()))
