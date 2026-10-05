"""Inspect one trajectory JSON: top-level keys, score, rollout shape."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)

print("top-level keys:", list(d.keys()))
for k, v in d.items():
    if hasattr(v, "__len__") and not isinstance(v, str):
        print(" ", k, type(v).__name__, len(v))
    else:
        s = str(v)
        print(" ", k, type(v).__name__, s[:200])
if "rollout" in d and isinstance(d["rollout"], dict):
    print("rollout keys:", list(d["rollout"].keys()))
