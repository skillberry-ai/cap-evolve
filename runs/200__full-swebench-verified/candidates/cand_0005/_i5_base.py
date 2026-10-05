import json
d = json.load(open("_baseline.json"))
print(type(d))
if isinstance(d, dict):
    print(list(d.keys())[:30])
    k0 = list(d.keys())[0]
    print("sample key:", k0)
    print(json.dumps(d[k0])[:600])
elif isinstance(d, list):
    print(len(d))
    print(json.dumps(d[0])[:600])
