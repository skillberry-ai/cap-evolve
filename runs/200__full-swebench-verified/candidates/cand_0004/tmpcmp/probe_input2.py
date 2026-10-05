import json, os

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
TRAJ = os.path.join(BASE, "trajectories")

fn = os.path.join(TRAJ, "astropy__astropy-13453__cand_0002__t0.json")
d = json.load(open(fn))
inp = d.get("input", "")
print("input len:", len(inp))
print(inp[:6000])
