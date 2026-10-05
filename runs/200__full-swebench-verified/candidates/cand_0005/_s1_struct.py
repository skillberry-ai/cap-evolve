import json, os, sys

fn = sys.argv[1] if len(sys.argv) > 1 else 'trajectories/django__django-10554__cand_0002__t0.json'
d = json.load(open(fn))
print('TOP KEYS:', list(d.keys()))
for k, v in d.items():
    if isinstance(v, dict):
        print(f'  {k}: dict keys={list(v.keys())[:20]}')
    elif isinstance(v, list):
        print(f'  {k}: list len={len(v)}')
    else:
        print(f'  {k}: {str(v)[:150]}')
