"""Inspect trajectory JSON deeper (optimizer scratch, not part of the candidate)."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)

ro = d["rollout"]
print("=== rollout.output keys:", list(ro["output"].keys()))
for k, v in ro["output"].items():
    print(f"--- output.{k}: {type(v).__name__} len={len(v) if hasattr(v,'__len__') else ''}")
    print(str(v)[:500])

print("=== rollout.trace keys:", list(ro["trace"].keys()))
for k, v in ro["trace"].items():
    print(f"--- trace.{k}: {type(v).__name__} len={len(v) if hasattr(v,'__len__') else ''}")
    print(str(v)[:800])

print("=== metadata:", json.dumps(ro["metadata"])[:800])
