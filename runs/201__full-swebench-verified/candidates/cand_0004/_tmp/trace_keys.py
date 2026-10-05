"""Dump the command sequence + outputs of a trajectory in compact form."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
tr = d["rollout"]["trace"]
print("trace keys:", list(tr.keys()))
for k, v in tr.items():
    if isinstance(v, list):
        print(f"  {k}: list of {len(v)}; first item keys:",
              list(v[0].keys()) if v and isinstance(v[0], dict) else (v[:1] if v else "empty"))
    elif isinstance(v, dict):
        print(f"  {k}: dict keys {list(v.keys())[:20]}")
    else:
        print(f"  {k}: {type(v).__name__} = {str(v)[:150]}")
