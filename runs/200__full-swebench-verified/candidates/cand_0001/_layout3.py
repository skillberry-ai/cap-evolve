import json, os

TRAJ = "trajectories"
d = json.load(open(os.path.join(TRAJ, "django__django-10554__seed__t0.json")))
u = [s["message"] for s in d["rollout"]["output"]["steps"] if s.get("source") == "user"][0]
print("===== chars [8600:9600] =====")
print(u[8600:9600])
