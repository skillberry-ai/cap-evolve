import json, os

TRAJ = "trajectories"
task = "django__django-16667"
p = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
d = json.load(open(p))
vs = d["rollout"]["metadata"].get("verifier_stdout", "")
print(len(vs))
i = vs.find("SWEBench results")
print(vs[max(0, i - 2500):i + 100])
