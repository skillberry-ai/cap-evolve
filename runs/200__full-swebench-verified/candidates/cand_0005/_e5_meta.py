import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# verifier stdout: is it truncated at 5000? Check the full metadata keys too
d = load("django__django-11555")
meta = d["rollout"].get("metadata") or {}
print("metadata keys:", list(meta.keys()))
vs = meta.get("verifier_stdout", "")
print("verifier_stdout len:", len(vs))
for k, v in meta.items():
    if isinstance(v, str):
        print(f"{k}: len={len(v)} head={v[:120]!r}")
    else:
        print(f"{k}: {json.dumps(v)[:400]}")
