import json, sys

d = json.load(open('_diag/cmp/baseline.json'))
print(type(d))
if isinstance(d, dict):
    for k in list(d.keys())[:25]:
        v = d[k]
        print(k, type(v), (len(v) if hasattr(v, '__len__') else v))
