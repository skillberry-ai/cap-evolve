import json, os

TRAJ = "trajectories"
p = os.path.join(TRAJ, "django__django-16667__cand_0002__t0.json")
d = json.load(open(p))
s20 = d["rollout"]["output"]["steps"][20]
c = s20["observation"]["results"][0]["content"]
j = json.loads(c)
print("elided:", j.get("elided_chars"))
tail = j.get("output_tail", "")
print("TAIL:", tail[:4000])
