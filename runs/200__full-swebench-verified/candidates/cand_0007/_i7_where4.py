import json, os

TRAJ = "trajectories"
p = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(p))
out = d["rollout"]["output"]
steps = out["steps"]
s2 = steps[1]
m2 = s2.get("message", "")
print("TOTAL LEN:", len(m2))
# find the skill text boundaries
i1 = m2.find("You are an expert software engineer")
print("skill start at:", i1)
print("=== chars around skill start ===")
print(m2[i1-200:i1+400])
# Where does the issue end?
i2 = m2.find("You can execute bash commands")
print("workflow start at:", i2)
print("=== chars before workflow ===")
print(m2[i2-400:i2+100])
