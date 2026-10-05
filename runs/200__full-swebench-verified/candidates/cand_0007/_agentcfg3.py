import json

fn = 'trajectories/pylint-dev__pylint-4661__seed__t0.json'
d = json.load(open(fn))
out = ((d.get('rollout') or {}).get('output')) or {}
extra = ((out.get('agent') or {}).get('extra')) or {}
cfg = extra.get('agent_config') or {}
for k in cfg:
    v = cfg[k]
    if isinstance(v, str) and len(v) > 500:
        print(f"--- {k} (len {len(v)}) first 200 chars ---")
        print(v[:200])
    else:
        print(f"--- {k} ---")
        print(v if isinstance(v, str) else json.dumps(v)[:400])
