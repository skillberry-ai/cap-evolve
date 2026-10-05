import json, sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
steps = d["rollout"]["trace"]["steps"]
a = d["rollout"]["trace"]["agent"]
print("AGENT KEYS:", json.dumps(a, indent=1)[:800])
fm = d["rollout"]["trace"]["final_metrics"]
print("FINAL METRICS:", json.dumps(fm, indent=1)[:600])
print()
for s in steps:
    msg = s.get("message", "")
    if isinstance(msg, str) and len(msg) == 0:
        print(f"### [{s.get('step_id')}] EMPTY agent step — raw json:")
        print(json.dumps(s, indent=1)[:900])
        break
