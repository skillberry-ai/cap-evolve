import json, sys, os

TRAJ = 'trajectories'
d = json.load(open('trajectories/django__django-12325__seed__t0.json'))
r = d['rollout']
print('rollout keys:', list(r.keys()))
out = r.get('output')
print('output keys:', list(out.keys()) if isinstance(out, dict) else out)

def walk(o, path='', depth=0):
    if depth > 4: return
    if isinstance(o, dict):
        for k, v in o.items():
            desc = (str(v)[:70] if not isinstance(v, (dict, list)) else f'len={len(v)}')
            print('  ' * depth + path + '/' + k, type(v).__name__, desc)
            if isinstance(v, (dict, list)):
                walk(v, path + '/' + k, depth + 1)
    elif isinstance(o, list) and o:
        print('  ' * depth + path + '[0]', type(o[0]).__name__)
        walk(o[0], path + '[0]', depth + 1)

walk(r)
