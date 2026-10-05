import json

d = json.load(open("_baseline.json"))
for split in ("val", "train"):
    s = d[split]
    print(f"== {split}: keys={list(s.keys())[:12]}")
    tasks = s.get("tasks") or s.get("per_task") or {}
    if isinstance(tasks, dict):
        for k, v in list(tasks.items())[:5]:
            print("   ", k, json.dumps(v)[:160])
    for k in ("mean", "reward", "n"):
        if k in s:
            print("   ", k, "=", s[k])
