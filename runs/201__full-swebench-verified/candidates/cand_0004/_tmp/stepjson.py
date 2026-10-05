"""Explore one step's full JSON to see where the command/observation lives."""
import json
import sys

d = json.load(open(sys.argv[1]))
steps = d["rollout"]["trace"]["steps"]
for i in (4, 5, 6):
    print(f"===== STEP {i} =====")
    print(json.dumps(steps[i], indent=1)[:2500])
    print()
