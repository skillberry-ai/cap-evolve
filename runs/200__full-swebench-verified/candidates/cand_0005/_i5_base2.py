import json

d = json.load(open("_baseline.json"))
val = d["val"]
per = val["per_task"]
print("baseline val reward:", val["reward"])
for t in per:
    print(f"{t['task_id']:44s} {t['reward']:5.2f}")
