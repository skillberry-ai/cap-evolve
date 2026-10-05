import json

fn = "trajectories/django__django-10554__cand_0002__t0.json"
d = json.load(open(fn))
r = d["rollout"]
out = r.get("output") or {}
extra = (out.get("agent") or {}).get("extra") or {}
cfg = extra.get("agent_config") or {}
print(cfg["instance_template"])
