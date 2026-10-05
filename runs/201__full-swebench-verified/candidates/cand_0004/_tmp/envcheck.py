import json, os, glob

TRAJ = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004/trajectories"

# Look for verifier stdout markers showing which python ran the eval, and check for
# 'conda' activation, 'testbed' env usage, /opt/miniconda3/envs/testbed markers
for f in sorted(glob.glob(os.path.join(TRAJ, "*.json"))):
    data = json.load(open(f))
    tid = data["score"]["task_id"]
    md = data["rollout"].get("metadata") or {}
    so = md.get("verifier_stdout") or ""
    hits = []
    for pat in ("envs/testbed", "miniconda3/envs", "/opt/conda", "conda run", "testbed/bin"):
        if pat in so:
            hits.append(pat)
    if hits:
        print(f"{tid} reward={data['score']['reward']}: {hits}")
