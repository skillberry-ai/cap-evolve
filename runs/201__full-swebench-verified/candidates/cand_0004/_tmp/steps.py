"""Dump the steps of a trajectory in a readable form.

Usage: python3 _tmp/steps.py <trajectory.json> [--full] [--range N:M]
"""
import json
import sys

path = sys.argv[1]
full = "--full" in sys.argv
rng = None
for a in sys.argv:
    if a.startswith("--range"):
        rng = a.split("=", 1)[1] if "=" in a else None

with open(path) as f:
    d = json.load(f)

steps = d["rollout"]["trace"]["steps"]
print(f"total steps: {len(steps)}")
for i, s in enumerate(steps):
    print(f"\n===== step {i} keys={list(s.keys())}")
    for k, v in s.items():
        if isinstance(v, str):
            if full:
                print(f"  [{k}] {v}")
            else:
                print(f"  [{k}] {v[:300]}")
        else:
            print(f"  [{k}] {type(v).__name__} {json.dumps(v)[:300]}")
