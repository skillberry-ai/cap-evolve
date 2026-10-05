"""Check the verifier stdout for pass/fail signals in a trajectory."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)

md = d["rollout"]["metadata"]
print("TASK:", d["score"]["task_id"], "reward:", d["score"]["reward"])
vs = md.get("verifier_stdout", "")
print("verifier_stdout length:", len(vs))
print("--- last 3000 chars ---")
print(vs[-3000:])
