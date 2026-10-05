import json, os, sys

TRAJ = 'trajectories'
fn = os.path.join(TRAJ, 'django__django-10554__cand_0002__t0.json')
d = json.load(open(fn))
ro = d.get('rollout') or {}
out = ro.get('output') or {}
ag = out.get('agent') or {}
cfg = (ag.get('extra') or {}).get('agent_config') or {}
it = cfg.get('instance_template') or ''
print('FULL instance_template:')
print(it)
