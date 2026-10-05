"""Dump a trajectory: input, rollout steps, score."""
import json
import sys

path = sys.argv[1]
maxlen = int(sys.argv[2]) if len(sys.argv) > 2 else 1200
with open(path) as f:
    d = json.load(f)
print("SCORE:", json.dumps(d.get("score"))[:500])
roll = d.get("rollout", {})
print("ROLLOUT keys:", list(roll.keys()))
for k, v in roll.items():
    if isinstance(v, list):
        print(f"-- {k}: list of {len(v)}")
    else:
        print(f"-- {k}: {type(v).__name__} = {str(v)[:200]}")
inp = d.get("input", "")
print("INPUT (first 3000):")
print(inp[:3000])
