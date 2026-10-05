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
print("metadata keys:", list(meta.keys()))
for k in ("verifier_stdout", "verifier_stderr"):
    v = meta.get(k, "")
    if v:
        print(f"--- {k} (len {len(v)}) ---")
        print(v[:4000])
