import json, os

TRAJ = "trajectories"
p = os.path.join(TRAJ, "django__django-16667__cand_0002__t0.json")
d = json.load(open(p))
s20 = d["rollout"]["output"]["steps"][20]
c = s20["observation"]["results"][0]["content"]
j = json.loads(c)
print("keys:", list(j.keys()))
print("returncode:", j.get("returncode"))
head = j.get("output_head", "")
tail = j.get("output_tail", "")
print("HEAD:", head[-3000:])
print("TAIL:", tail[:3000])
