import json
d = json.load(open("_baseline.json"))
val = d["val"]
pt = val["per_task"]
print(type(pt), len(pt))
print(json.dumps(pt[0])[:300])
for it in pt:
    r = it.get("reward", it.get("mean", None))
    print(f"{str(it.get('task', it.get('task_id', it.get('id','?')))):45s} {r}")
