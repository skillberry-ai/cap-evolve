import json, sys

p = sys.argv[1]
with open(p) as f:
    d = json.load(f)
steps = d["rollout"]["trace"]["steps"]
for s in steps[:3]:
    if s.get("source") in ("system", "user"):
        print("=" * 40, s.get("source"), "=" * 40)
        print(s.get("message"))
        print()
