import json

d = json.load(open("tmpcmp/baseline.json"))
for split in d:
    print(split, "reward", d[split].get("reward"))
    ids = [t["task_id"] for t in d[split]["per_task"]]
    print(len(ids), "tasks")
    print([i for i in ids if "django" in i][:60])
