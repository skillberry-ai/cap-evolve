"""Dump input type/content and step-level observations of test commands (optimizer scratch)."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
inp = d["input"]
print("input type:", type(inp).__name__)
if isinstance(inp, str):
    print("len:", len(inp))
    print(inp[:400])
    print("....")
    print(inp[-2500:])
else:
    print(json.dumps(inp)[:2500])
