import json, sys, os

p = sys.argv[1]
with open(p) as f:
    d = json.load(f)
print(type(d))
if isinstance(d, dict):
    print("KEYS:", list(d.keys()))
    for k, v in d.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            s = str(v)
            print(f"  {k} = {s[:300]}")
        elif isinstance(v, list):
            print(f"  {k} : list len {len(v)}")
            if v and isinstance(v[0], dict):
                print(f"    first item keys: {list(v[0].keys())}")
        elif isinstance(v, dict):
            print(f"  {k} : dict keys {list(v.keys())[:30]}")
