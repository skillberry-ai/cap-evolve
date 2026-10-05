import json, os

TRAJ = "trajectories"
p = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(p))
out = d["rollout"]["output"]
steps = out["steps"]
# find where the skill text appears: check system steps or first user step
s1 = steps[0]
m = s1.get("message", "")
print("STEP1 system message:")
print(m)
print("LENGTH:", len(m))
print()
s2 = steps[1]
m2 = s2.get("message", "")
print("STEP2 user message length:", len(m2))
print(m2[:1500])
