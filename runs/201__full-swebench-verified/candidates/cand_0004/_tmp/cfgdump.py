"""Dump the full agent_config from one trajectory to see the step/output limits."""
import json

d = json.load(open("trajectories/django__django-10554__seed__t0.json"))
extra = d["rollout"]["trace"]["agent"].get("extra") or {}
cfg = extra.get("agent_config") or {}
for k, v in cfg.items():
    print("==", k)
    print(str(v)[:600])
    print()
