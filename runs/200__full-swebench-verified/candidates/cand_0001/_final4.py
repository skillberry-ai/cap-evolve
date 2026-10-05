import json, os

TRAJ = "trajectories"
data = json.load(open(os.path.join(TRAJ, "django__django-10554__seed__t0.json")))
out = data["rollout"]["output"]
s = json.dumps(out, indent=1)
print("LEN", len(s))
print(s[3500:8000])
