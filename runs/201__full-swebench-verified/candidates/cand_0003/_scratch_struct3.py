import json, sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
tr = d["rollout"]["trace"]
for k, v in tr.items():
    print(f"trace.{k}: {type(v).__name__}" + (f" len={len(v)}" if isinstance(v, (list, dict, str)) else f" = {v}"))
out = d["rollout"]["output"]
for k, v in out.items():
    print(f"output.{k}: {type(v).__name__}" + (f" len={len(v)}" if isinstance(v, (list, dict, str)) else f" = {v}"))
md = d["rollout"]["metadata"]
for k, v in md.items():
    print(f"metadata.{k}: {type(v).__name__}" + (f" len={len(v)}" if isinstance(v, (list, dict, str)) else f" = {v}"))
