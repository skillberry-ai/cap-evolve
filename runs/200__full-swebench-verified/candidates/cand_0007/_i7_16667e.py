import json, os

TRAJ = "trajectories"
d = json.load(open(os.path.join(TRAJ, "django__django-16667__cand_0002__t0.json")))
steps = d["rollout"]["output"]["steps"]
s20 = steps[20]
c = s20["observation"]["results"][0]["content"]
j = json.loads(c)
head = j.get("output_head", "")
tail = j.get("output_tail", "")
print("HEAD last 3000:")
print(head[-3000:])
print()
print("=====TAIL first 2000:")
print(tail[:2000])
