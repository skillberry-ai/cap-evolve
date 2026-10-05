import json, os

TRAJ = "trajectories"
fn = "trajectories/django__django-10554__cand_0002__t0.json"
d = json.load(open(fn))
r = d["rollout"]
# dump top-level keys
print("top keys:", list(d.keys()))
print("rollout keys:", list(r.keys()))
out = r.get("output") or {}
print("output keys:", list(out.keys()))
extra = (out.get("agent") or {}).get("extra") or {}
print("agent.extra keys:", list(extra.keys()))
cfg = extra.get("agent_config") or {}
print("agent_config keys:", list(cfg.keys()))
for k, v in cfg.items():
    if isinstance(v, str):
        print(f"--- {k} (len {len(v)}) ---")
        print(v[:600])
        print("...")
    else:
        print(f"--- {k} ---", json.dumps(v)[:300])
