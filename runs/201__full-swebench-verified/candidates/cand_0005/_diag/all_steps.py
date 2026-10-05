"""Dump all steps with full detail, showing tool_calls and messages."""
import json
import sys

d = json.load(open(sys.argv[1]))
r = d["rollout"]
steps = r["trace"]["steps"]
print(f"### {r['task_id']}  reward={d['score'].get('reward')}")
print("### tool_calls:", json.dumps(r.get("tool_calls"))[:300])
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
hi = int(sys.argv[3]) if len(sys.argv) > 3 else len(steps)
maxlen = int(sys.argv[4]) if len(sys.argv) > 4 else 900
for i, s in enumerate(steps):
    if not (lo <= i <= hi):
        continue
    src = s.get("source")
    m = s.get("message", "")
    if not isinstance(m, str):
        m = json.dumps(m)
    if m.strip() or src != "agent":
        print(f"\n===== STEP {i} [{src}] =====\n{m[:maxlen]}")
