"""Explore rollout.metadata (verdict details)."""
import json
import sys

d = json.load(open(sys.argv[1]))
md = d["rollout"]["metadata"]
for k, v in md.items():
    s = str(v)
    print(f"== {k}: {s[:2000]}")
    print()
