"""Dump observations structure for all steps of one trajectory (optimizer scratch)."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
steps = d["rollout"]["trace"]["steps"]
s0 = steps[3]
print(json.dumps(s0, indent=1)[:3000])
