import json

d = json.load(open('./_i6_baseline.json'))
val = d['val']
pt = val.get('per_task') or []
print(f"n_val_tasks={len(pt)}")
for t in pt:
    print(f"  {t.get('task_id'):45s} reward={t.get('reward')}")
