import json, os, sys

TRAJ = "trajectories"

t = sys.argv[1] if len(sys.argv) > 1 else "django__django-10554"
d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
print('TOP KEYS:', list(d.keys()))
r = d['rollout']
print('ROLLOUT KEYS:', list(r.keys()))
print('score:', d.get('score'))
tr = r.get('trace') or {}
print('TRACE KEYS:', list(tr.keys()))
steps = tr.get('steps') or []
print('N STEPS:', len(steps))
if steps:
    print('STEP KEYS:', list(steps[0].keys()))
    print(json.dumps(steps[0], indent=1)[:1500])
out = r.get('output')
print('OUTPUT TYPE:', type(out))
print(json.dumps(out)[:800] if out else '(None)')
md = r.get('metadata') or {}
print('METADATA KEYS:', list(md.keys()))
