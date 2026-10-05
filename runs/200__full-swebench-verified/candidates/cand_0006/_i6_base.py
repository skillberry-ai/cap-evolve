import json

d = json.load(open('baseline.json'))
print(type(d).__name__, len(d) if hasattr(d, '__len__') else '')
if isinstance(d, dict):
    for k in list(d.keys())[:30]:
        v = d[k]
        print(f"{k}: {type(v).__name__} {str(v)[:150]}")
elif isinstance(d, list):
    print(json.dumps(d[0], indent=1)[:1500])
