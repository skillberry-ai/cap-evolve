import json, os

TRAJ = "trajectories"
d = json.load(open(os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")))
u = [s["message"] for s in d["rollout"]["output"]["steps"] if s.get("source") == "user"][0]
i = u.find("You are an expert software engineer")
j = u.find("Please solve this issue")
print("full user message length:", len(u))
print("--- first 400 chars ---")
print(u[:400])
print("--- chars around 'Please solve' ---")
print(u[max(0,j-200):j+100])
