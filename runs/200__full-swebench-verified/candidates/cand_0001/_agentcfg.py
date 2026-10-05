import json, os, sys

TRAJ = "trajectories"
d = json.load(open(os.path.join(TRAJ, "django__django-10554__seed__t0.json")))
r = d["rollout"]
ac = ((r.get("output") or {}).get("agent") or {}).get("extra") or {}
cfg = ac.get("agent_config") or {}
print("AGENT CONFIG KEYS:", list(cfg.keys()))
for k, v in cfg.items():
    print(f"--- {k} ---")
    print(v if isinstance(v, str) else json.dumps(v)[:3000])
    print()
