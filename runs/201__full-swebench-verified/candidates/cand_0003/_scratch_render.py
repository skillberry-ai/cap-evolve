import json, sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
steps = d["rollout"]["trace"]["steps"]
for s in steps:
    src = s.get("source", "?")
    msg = s.get("message", "")
    if isinstance(msg, dict):
        msg = json.dumps(msg)
    msg = msg.replace("\n", " ⏎ ")
    print(f"[{s.get('step_id')}] {src}: {msg[:400]}")
    print("---")
