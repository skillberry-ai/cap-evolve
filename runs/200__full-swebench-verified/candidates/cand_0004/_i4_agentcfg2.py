import json, os
TRAJ = "trajectories"
fn = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(fn))
out = d.get("rollout", {}).get("output") or {}
cfg = ((out.get("agent") or {}).get("extra") or {}).get("agent_config") or {}
it = cfg.get("instance_template", "")
print(it)
