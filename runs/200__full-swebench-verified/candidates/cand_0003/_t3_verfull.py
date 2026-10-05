import json, sys, os, re

p = sys.argv[1]
with open(p) as f:
    d = json.load(f)
md = d["rollout"].get("metadata") or {}
vs = md.get("verifier_stdout", "") or ""
print("LEN:", len(vs))
print(vs)
