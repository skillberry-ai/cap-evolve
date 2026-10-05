import json, os

TRAJ = "trajectories"
p = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(p))
out = d["rollout"]["output"]
steps = out["steps"]
s2 = steps[1]
m2 = s2.get("message", "")
# print the last 7000 chars of user message (the issue + appended skill text?)
print(m2[4000:])
