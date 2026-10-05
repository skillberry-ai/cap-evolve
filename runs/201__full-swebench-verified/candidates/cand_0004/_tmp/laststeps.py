"""Inspect the last steps of a trajectory in full detail."""
import json
import sys

d = json.load(open(sys.argv[1]))
steps = (d["rollout"]["output"] or {}).get("steps", [])
n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
for s in steps[-n:]:
    print("=" * 80)
    print(json.dumps(s, indent=2)[:3000])
