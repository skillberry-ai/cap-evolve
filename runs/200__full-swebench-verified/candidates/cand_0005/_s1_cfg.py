import json, os, sys

fn = 'trajectories/django__django-10554__cand_0002__t0.json'
d = json.load(open(fn))
out = ((d.get('rollout') or {}).get('output')) or {}
extra = ((out.get('agent') or {}).get('extra')) or {}
cfg = extra.get('agent_config') or {}
for k, v in cfg.items():
    if isinstance(v, str):
        print(f"===== {k} (len {len(v)}) =====")
        print(v)
    else:
        print(f"===== {k} =====")
        print(json.dumps(v, indent=1)[:2000])
