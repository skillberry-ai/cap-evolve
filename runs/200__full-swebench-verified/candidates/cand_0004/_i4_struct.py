import json, os, sys

TRAJ = 'trajectories'

fn = os.path.join(TRAJ, 'django__django-10554__cand_0002__t0.json')
d = json.load(open(fn))
print('TOP KEYS:', list(d.keys()))
print('score:', d.get('score'))
ro = d.get('rollout') or {}
print('rollout keys:', list(ro.keys()))
print('metadata keys:', list((ro.get('metadata') or {}).keys()))
out = ro.get('output') or {}
print('output keys:', list(out.keys()))
st = (ro.get('trace') or {}).get('steps') or []
print('trace steps:', len(st))
if st:
    s = st[0]
    print('step0 keys:', list(s.keys()))
    print('step0 source:', s.get('source'))
    print(json.dumps(s, indent=1)[:1500])
