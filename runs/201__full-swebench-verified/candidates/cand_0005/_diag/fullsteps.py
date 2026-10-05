"""Dump full steps of a trajectory (all fields)."""
import json
import sys

path = sys.argv[1]
d = json.load(open(path))
r = d["rollout"]
steps = r["trace"]["steps"]
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
hi = int(sys.argv[3]) if len(sys.argv) > 3 else len(steps)
for s in steps[lo:hi]:
    print(f"===== {s.get('step_id')} [{s.get('source')}] =====")
    print(json.dumps(s, indent=1)[:6000])
    print()
