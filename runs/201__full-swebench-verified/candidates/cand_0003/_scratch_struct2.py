import json, sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
r = d["rollout"]
for k, v in r.items():
    print(f"rollout.{k}: {type(v).__name__}" + (f" len={len(v)}" if isinstance(v, (list, dict, str)) else f" = {v}"))
s = d["score"]
for k, v in s.items():
    print(f"score.{k}: {type(v).__name__}" + (f" len={len(v)}" if isinstance(v, (list, dict, str)) else f" = {v}"))
