import json
d = json.load(open("trajectories/sympy__sympy-15599__seed__t0.json"))
ro = d.get("rollout") or {}
out = ro.get("output") or {}
cfg = (out.get("agent") or {}).get("extra", {}).get("agent_config") or {}
for k, v in cfg.items():
    if k != "instance_template":
        print(k, "=", json.dumps(v)[:300])
