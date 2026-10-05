import json, os

b = json.load(open("_baseline.json"))
per = b["val"]["per_task"]
print("=== VAL failing (reward 0.0, not errored) ===")
for t in per:
    if t["reward"] == 0.0 and not t["raw"]["errored"]:
        print(t["task_id"], "| errored_trials:", t["raw"]["errored_trials"], "| feedback:", t["feedback"][:120])
print()
print("=== VAL errored ===")
for t in per:
    if t["raw"]["errored"]:
        print(t["task_id"], t["raw"])
