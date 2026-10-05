import json
d = json.load(open("_baseline.json"))
print(type(d))
if isinstance(d, dict):
    print(list(d.keys())[:20])
    for k in list(d.keys())[:3]:
        v = d[k]
        print("---", k, type(v), (list(v.keys())[:10] if isinstance(v, dict) else str(v)[:100]))
else:
    print(len(d))
    print(json.dumps(d[0])[:400])
