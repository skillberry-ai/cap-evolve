import json, os
TRAJ = "trajectories"
fn = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(fn))
out = d.get("rollout", {}).get("output") or {}
agent = out.get("agent") or {}
print("agent keys:", list(agent.keys()))
extra = agent.get("extra") or {}
print("extra keys:", list(extra.keys()))
cfg = extra.get("agent_config") or {}
for k, v in cfg.items():
    if isinstance(v, str) and len(v) > 300:
        print(f"--- {k} (len={len(v)}) ---")
        print(v[:150], "...")
    else:
        print(f"--- {k} ---")
        print(json.dumps(v)[:400] if not isinstance(v, str) else v[:400])
