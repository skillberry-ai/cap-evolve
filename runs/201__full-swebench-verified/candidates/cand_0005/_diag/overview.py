"""Overview of a trajectory: steps, commands, final state."""
import json
import sys

path = sys.argv[1]
maxprint = int(sys.argv[2]) if len(sys.argv) > 2 else 80
d = json.load(open(path))
r = d["rollout"]
steps = r["trace"]["steps"]
print("top keys:", list(d.keys()))
print("rollout keys:", list(r.keys()))
for k in r:
    if k not in ("trace",):
        v = r[k]
        print(f"  {k}: {str(v)[:300]}")
print("num steps:", len(steps))
for s in steps:
    src = s.get("source")
    msg = s.get("message", "")
    if isinstance(msg, dict):
        msg = json.dumps(msg)
    txt = str(msg).replace("\n", " ¶ ")[:maxprint]
    print(f"--- {s.get('step_id')} [{src}] {txt}")
