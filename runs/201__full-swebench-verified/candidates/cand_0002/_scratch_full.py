"""Dump full steps including tool/command payloads (optimizer scratch)."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)

ro = d["rollout"]
tr = ro["trace"]
steps = tr["steps"]
score = d["score"]

print(f"### TASK {score['task_id']}  reward={score['reward']}  n_steps={len(steps)}")
print(f"### feedback: {score.get('feedback','')[:300]}")

# Print every step's full JSON for non-empty ones
for s in steps:
    msg = (s.get("message") or "")
    if msg.strip():
        print(f"\n===== STEP {s.get('step_id')} [{s.get('source')}] =====")
        print(msg[:2500])
    else:
        # dump whole step dict to find command fields
        extra = {k: v for k, v in s.items() if k not in ("step_id", "source", "message")}
        if extra:
            print(f"\n===== STEP {s.get('step_id')} [{s.get('source')}] (extra) =====")
            print(json.dumps(extra)[:2500])
        else:
            print(f"----- STEP {s.get('step_id')} [{s.get('source')}] EMPTY")
