import json, sys

p = sys.argv[1]
with open(p) as f:
    d = json.load(f)
md = d["rollout"].get("metadata") or {}
vs = md.get("verifier_stdout", "") or ""
# print only first 3000 chars
print(vs[:3500])
