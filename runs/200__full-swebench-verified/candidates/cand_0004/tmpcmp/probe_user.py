import json, os

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
TRAJ = os.path.join(BASE, "trajectories")

fn = os.path.join(TRAJ, "astropy__astropy-13453__cand_0002__t0.json")
d = json.load(open(fn))
# The user message is steps[1]. Print it in full to see what instructions the agent gets.
steps = d["rollout"]["output"]["steps"]
u = steps[1]
msg = u.get("message", "")
print("USER MESSAGE len:", len(msg))
print(msg)
