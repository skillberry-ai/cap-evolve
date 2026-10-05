import json, os, sys

TRAJ = "trajectories"
d = json.load(open(os.path.join(TRAJ, "django__django-10554__seed__t0.json")))
steps = d["rollout"]["output"]["steps"]
sysmsgs = [s["message"] for s in steps if s.get("source") == "system"]
print("SYSTEM MESSAGE:")
print(sysmsgs[0] if sysmsgs else "(none)")
# Where does skill text begin/end within user message 1?
u = [s["message"] for s in steps if s.get("source") == "user"][0]
print("expert-engineer at:", u.find("You are an expert software engineer"))
print("critical rules end at:", u.find("potential regression."))
print("===== chars [7000:8000] =====")
print(u[7000:8000])
