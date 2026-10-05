import json, os

TRAJ = "trajectories"
for task in ["django__django-12039", "django__django-13401", "django__django-15930"]:
    p = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(p))
    vs = d["rollout"]["metadata"].get("verifier_stdout", "")
    i = vs.find("SWEBench results")
    print("##", task, "->", vs[i:i + 60].replace("\n", " "))
