import json, os, sys

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

task = sys.argv[1]
d = load(task)
r = d["rollout"]
meta = r.get("metadata") or {}
vs = meta.get("verifier_stdout", "") or ""
vse = meta.get("verifier_stderr", "") or ""
rj = meta.get("reward_json") or {}
print("== reward_json:", json.dumps(rj)[:600])
print("== verifier_stdout (len", len(vs), ") tail:")
print(vs[-3500:])
if vse:
    print("== verifier_stderr (len", len(vse), ") tail:")
    print(vse[-1500:])
