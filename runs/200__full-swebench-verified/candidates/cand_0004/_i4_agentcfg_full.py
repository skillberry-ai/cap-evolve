import json, os, sys

TRAJ = 'trajectories'
fn = os.path.join(TRAJ, 'django__django-10554__cand_0002__t0.json')
d = json.load(open(fn))
ro = d.get('rollout') or {}
out = ro.get('output') or {}
ag = out.get('agent') or {}
print('agent keys:', list(ag.keys()))
extra = ag.get('extra') or {}
print('extra keys:', list(extra.keys()))
cfg = extra.get('agent_config') or {}
for k, v in cfg.items():
    if isinstance(v, str) and len(v) > 300:
        print(f"--- {k} (len {len(v)}) ---")
        print(v[:1200])
        print("...")
    else:
        print(f"--- {k} ---")
        print(v if isinstance(v, str) else json.dumps(v)[:500])
steps = (ro.get('trace') or {}).get('steps') or []
# print system + first user message fully
for s in steps[:2]:
    print("=" * 80)
    print(s.get('source'), '::')
    print((s.get('message') or '')[:3000])
