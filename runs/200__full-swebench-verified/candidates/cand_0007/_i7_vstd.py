import json, os

TRAJ = "trajectories"
p = os.path.join(TRAJ, "django__django-16667__cand_0002__t0.json")
d = json.load(open(p))
md = d["rollout"]["metadata"]
ve = md.get("verifier_stderr", "") or ""
print("verifier_stderr len:", len(ve))
print(ve[:3000])
print(".....")
rj = md.get("reward_json")
print("reward_json:", json.dumps(rj)[:1000])
