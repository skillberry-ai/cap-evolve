"""Dump raw steps of a trajectory: source, and full message (truncated)."""
import json
import sys

d = json.load(open(sys.argv[1]))
steps = d["rollout"]["trace"]["steps"]
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
hi = int(sys.argv[3]) if len(sys.argv) > 3 else len(steps)
maxlen = int(sys.argv[4]) if len(sys.argv) > 4 else 700
print(f"### {d['rollout']['task_id']}  reward={d['score'].get('reward')}")
for i, s in enumerate(steps):
    if not (lo <= i <= hi):
        continue
    src = s.get("source")
    m = s.get("message", "")
    if not isinstance(m, str):
        m = json.dumps(m)
    print(f"\n===== STEP {i} [{src}] =====\n{m[:maxlen]}")
