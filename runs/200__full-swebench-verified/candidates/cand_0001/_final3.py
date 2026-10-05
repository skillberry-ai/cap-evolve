import json, os

TRAJ = "trajectories"
data = json.load(open(os.path.join(TRAJ, "django__django-10554__seed__t0.json")))
out = data["rollout"]["output"]
print(json.dumps(out, indent=1)[:4000])
