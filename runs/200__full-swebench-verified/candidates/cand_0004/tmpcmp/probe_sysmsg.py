import json, os

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
TRAJ = os.path.join(BASE, "trajectories")

fn = os.path.join(TRAJ, "astropy__astropy-13453__cand_0002__t0.json")
d = json.load(open(fn))
steps = d["rollout"]["output"]["steps"]
s0 = steps[0]
print("SYSTEM MESSAGE FULL:")
print(s0.get("message"))
print()
print("=" * 100)
print("INPUT (task prompt) first 2000 chars:")
print(d.get("input", "")[:2000])
