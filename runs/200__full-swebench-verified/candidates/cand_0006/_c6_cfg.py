import json

fn = 'trajectories/pylint-dev__pylint-4661__cand_0002__t0.json'
d = json.load(open(fn))
out = ((d.get('rollout') or {}).get('output')) or {}
extra = ((out.get('agent') or {}).get('extra')) or {}
cfg = extra.get('agent_config') or {}
print(sorted(cfg.keys()))
for k in sorted(cfg.keys()):
    v = cfg[k]
    if isinstance(v, str) and len(v) > 400:
        print(f"--- {k}: len={len(v)} first 120: {v[:120]!r}")
    else:
        print(f"--- {k}: {json.dumps(v)[:200]}")
