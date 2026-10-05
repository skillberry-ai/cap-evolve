"""Deeper inspection of trajectory JSON structure."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)

print("=== input (first 2000 chars) ===")
print(d["input"][:2000])
print("...")
print("=== score ===")
print(json.dumps(d["score"], indent=2)[:2000])
print("=== rollout keys ===")
for k, v in d["rollout"].items():
    print(" ", k, type(v).__name__, (len(v) if hasattr(v, "__len__") else v))
