import json, os, glob

TRAJ = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004/trajectories"

for f in sorted(glob.glob(os.path.join(TRAJ, "*.json"))):
    data = json.load(open(f))
    tid = data["score"]["task_id"]
    reward = data["score"]["reward"]
    md = data["rollout"].get("metadata") or {}
    so = (md.get("verifier_stdout") or "")[:600].replace("\n", " | ")
    se = (md.get("verifier_stderr") or "")[:400].replace("\n", " | ")
    print("=" * 100)
    print(f"{tid}  reward={reward}")
    print("STDOUT:", so)
    if se.strip():
        print("STDERR:", se)
