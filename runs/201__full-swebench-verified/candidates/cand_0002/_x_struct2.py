import json, sys

p = sys.argv[1]
with open(p) as f:
    d = json.load(f)
r = d["rollout"]
out = r["output"]
print(json.dumps({k: v for k, v in out.items() if k != "trajectory"}, indent=2)[:3000])
traj = out.get("trajectory", [])
print("N steps:", len(traj))
if traj:
    print("step0 keys:", list(traj[0].keys()))
    print("last keys:", list(traj[-1].keys()))
