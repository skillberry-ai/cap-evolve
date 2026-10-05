import json, os

TRAJ = "trajectories"
d = json.load(open(os.path.join(TRAJ, "django__django-10554__seed__t0.json")))
steps = d["rollout"]["output"]["steps"]
user_msgs = [s["message"] for s in steps if s.get("source") == "user"]
u = user_msgs[0]
# Where does the "expert software engineer" prompt appear? Find it and print 800 chars around "Critical rules"
i = u.find("You are an expert software engineer")
print("found at:", i)
j = u.find("## Critical rules")
print("critical rules at:", j)
print(u[j:j+2200])
