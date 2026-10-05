"""Explore rollout.output structure."""
import json
import sys

d = json.load(open(sys.argv[1]))
out = d["rollout"]["output"]
def walk(o, prefix="", depth=0):
    if depth > 4:
        print(prefix, "...")
        return
    if isinstance(o, dict):
        for k, v in o.items():
            walk(v, f"{prefix}.{k}", depth + 1)
    elif isinstance(o, list):
        print(f"{prefix}: list[{len(o)}]")
        if o:
            walk(o[0], f"{prefix}[0]", depth + 1)
    else:
        s = str(o)
        print(f"{prefix}: {type(o).__name__} = {s[:120]!r}")
walk(out)
