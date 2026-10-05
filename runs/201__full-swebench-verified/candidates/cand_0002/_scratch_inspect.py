"""Inspect trajectory JSON structure (optimizer scratch, not part of the candidate)."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
print(type(d))


def describe(v, depth=0):
    if isinstance(v, dict):
        for k, vv in v.items():
            print("  " * depth + f"{k}: {type(vv).__name__} " + (f"len={len(vv)}" if isinstance(vv, (list, dict)) else repr(vv)[:150]))
            if depth < 1 and isinstance(vv, (dict,)) :
                describe(vv, depth + 1)
            elif depth < 1 and isinstance(vv, list) and vv:
                print("  " * (depth+1) + f"[0]: {type(vv[0]).__name__}")
                if isinstance(vv[0], dict):
                    describe(vv[0], depth + 2)
    elif isinstance(v, list):
        print("list len", len(v))


describe(d)
