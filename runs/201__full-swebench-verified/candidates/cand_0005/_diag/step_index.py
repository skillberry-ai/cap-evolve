"""Look at the actual trace JSON in full detail - check message content of every step."""
import json
import sys

d = json.load(open(sys.argv[1]))
r = d["rollout"]
steps = r["trace"]["steps"]
print(f"### {r['task_id']}  reward={d['score'].get('reward')}  nsteps={len(steps)}")
for i, s in enumerate(steps):
    src = s.get("source")
    m = s.get("message", "")
    if not isinstance(m, str):
        m = json.dumps(m)
    # print first 200 chars of each message with any tool call markers
    head = m.replace("\n", " | ")[:250]
    print(f"{i:>3} [{src:>7}] {head}")
