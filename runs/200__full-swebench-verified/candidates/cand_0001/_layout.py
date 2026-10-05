import json, os, sys

TRAJ = "trajectories"
d = json.load(open(os.path.join(TRAJ, "django__django-10554__seed__t0.json")))
steps = d["rollout"]["output"]["steps"]
u = [s["message"] for s in steps if s.get("source") == "user"][0]
print("LEN:", len(u))
i = u.find("You are an expert software engineer")
print("expert-engineer at:", i)
print("===== chars [2600:3200] =====")
print(u[2600:3200])
print("===== chars [5000:7000] =====")
print(u[5000:7000])
