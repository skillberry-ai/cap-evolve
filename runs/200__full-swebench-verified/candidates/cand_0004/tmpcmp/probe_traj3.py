import json, os

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
TRAJ = os.path.join(BASE, "trajectories")

fn = os.path.join(TRAJ, "astropy__astropy-13453__cand_0002__t0.json")
d = json.load(open(fn))
steps = d["rollout"]["output"]["steps"]
for i, s in enumerate(steps[:10]):
    print("=== step", i, "source:", s.get("source"), "step_id:", s.get("step_id"))
    print(json.dumps(s, default=str)[:600])
