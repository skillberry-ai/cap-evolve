"""Show raw step messages (strings) for a trajectory."""
import json
import sys

d = json.load(open(sys.argv[1]))
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
hi = int(sys.argv[3]) if len(sys.argv) > 3 else 10
ml = int(sys.argv[4]) if len(sys.argv) > 4 else 700
steps = d["rollout"]["trace"]["steps"]
for i, s in enumerate(steps):
    if not (lo <= i < hi):
        continue
    m = s.get("message", "")
    print(f"===== STEP {i} [{s.get('source')}] =====")
    print(str(m)[:ml])
    print()
