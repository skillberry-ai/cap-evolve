import json, os

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
TRAJ = os.path.join(BASE, "trajectories")

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

d = load("astropy__astropy-13453")
meta = d["rollout"].get("metadata") or {}
vs = meta.get("verifier_stdout", "") or ""
print("LEN:", len(vs))
print(vs[4000:5000])
