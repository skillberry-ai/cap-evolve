import json, os

TRAJ = "trajectories"
p = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(p))
out = d["rollout"]["output"]
extra = out.get("agent", {}).get("extra", {})
cfg = extra.get("agent_config", {})
it = cfg["instance_template"]
print(it)
