import json, os, sys

fn = sys.argv[1] if len(sys.argv) > 1 else 'trajectories/django__django-10554__cand_0002__t0.json'
d = json.load(open(fn))
print('TOP KEYS:', list(d.keys()))
for k in d.keys():
    v = d[k]
    if isinstance(v, dict):
        print(k, 'dict keys:', list(v.keys()))
    elif hasattr(v, '__len__'):
        print(k, type(v).__name__, 'len', len(v))
    else:
        print(k, type(v).__name__, v)
