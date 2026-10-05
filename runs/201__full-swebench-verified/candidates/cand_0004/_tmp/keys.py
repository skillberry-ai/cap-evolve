import json, sys, os

TRAJ = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004/trajectories"

f = os.path.join(TRAJ, "django__django-10554__seed__t0.json")
data = json.load(open(f))
steps = data["rollout"]["output"]["steps"]
print("step keys:", sorted(steps[3].keys()))
print(json.dumps(steps[3], indent=1)[:3000])
