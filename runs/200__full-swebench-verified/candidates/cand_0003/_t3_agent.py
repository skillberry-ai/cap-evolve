import json, sys

p = sys.argv[1]
with open(p) as f:
    d = json.load(f)
tr = d["rollout"]["trace"]
ag = tr.get("agent", {})
print(json.dumps(ag, indent=1)[:6000])
