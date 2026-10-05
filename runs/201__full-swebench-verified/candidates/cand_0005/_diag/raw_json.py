"""Dump the raw JSON of specific steps to understand the format."""
import json
import sys

d = json.load(open(sys.argv[1]))
r = d["rollout"]
steps = r["trace"]["steps"]
idxs = [int(x) for x in sys.argv[2].split(",")]
for i in idxs:
    if i < len(steps):
        print(f"===== STEP {i} RAW =====")
        print(json.dumps(steps[i], indent=1)[:4000])
        print()
