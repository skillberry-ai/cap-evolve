"""Dump verifier metadata for one trajectory."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)

r = d["rollout"]
md = r.get("metadata") or {}
print("harbor_reward:", md.get("harbor_reward"))
rj = md.get("reward_json")
print("reward_json:", json.dumps(rj)[:300] if rj else None)
vs = md.get("verifier_stdout")
if isinstance(vs, str):
    print("verifier_stdout (last 3000):")
    print(vs[-3000:])
else:
    print("verifier_stdout:", vs)
vse = md.get("verifier_stderr")
if isinstance(vse, str):
    print("verifier_stderr (last 1000):")
    print(vse[-1000:])
