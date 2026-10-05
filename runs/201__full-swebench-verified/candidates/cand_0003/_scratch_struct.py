import json, sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
print(type(d))
if isinstance(d, dict):
    for k in d.keys():
        v = d[k]
        print(f"  {k}: {type(v).__name__}" + (f" len={len(v)}" if isinstance(v, (list, dict, str)) else f" = {v}"))
