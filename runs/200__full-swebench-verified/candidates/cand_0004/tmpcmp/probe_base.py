import json, os, sys

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
TRAJ = os.path.join(BASE, "trajectories")

d = json.load(open(os.path.join(BASE, "tmpcmp", "baseline.json")))
print("baseline.json type:", type(d).__name__)
if isinstance(d, dict):
    print("keys:", list(d.keys())[:15])
