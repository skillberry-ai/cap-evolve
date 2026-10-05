import json, sys

p = sys.argv[1]
with open(p) as f:
    d = json.load(f)
md = d["rollout"].get("metadata") or {}
vs = md.get("verifier_stdout") or ""
lines = vs.splitlines()
# find the ERROR block with traceback
for i, ln in enumerate(lines):
    if ln.startswith("ERROR:"):
        print("\n".join(lines[i:i+40]))
        print("~~~~")
        break
