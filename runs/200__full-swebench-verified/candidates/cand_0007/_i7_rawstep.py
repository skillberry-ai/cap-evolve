import json, sys

d = json.load(open(sys.argv[1]))
steps = d["rollout"]["output"]["steps"]
idx = int(sys.argv[2])
s = steps[idx]
print("source:", s.get("source"))
print(json.dumps(s, indent=1)[:6000])
