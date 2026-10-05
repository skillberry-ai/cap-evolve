"""Dump trace structure of a trajectory."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)

print("=== output keys ===")
for k, v in d["rollout"]["output"].items():
    print(" ", k, type(v).__name__, (len(v) if hasattr(v, "__len__") else str(v)[:100]))
print("=== trace keys ===")
for k, v in d["rollout"]["trace"].items():
    print(" ", k, type(v).__name__, (len(v) if hasattr(v, "__len__") else str(v)[:100]))
print("=== metadata ===")
print(json.dumps(d["rollout"]["metadata"], indent=2)[:1000])
