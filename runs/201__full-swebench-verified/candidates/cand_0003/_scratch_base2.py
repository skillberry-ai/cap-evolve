import json

d = json.load(open("_baseline.json"))
pt = d["val"]["per_task"]
print(type(pt).__name__, len(pt))
items = list(pt.items())[:3] if isinstance(pt, dict) else pt[:3]
print(json.dumps(items, indent=1)[:900])
