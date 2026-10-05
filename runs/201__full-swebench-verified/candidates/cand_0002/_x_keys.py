import json, sys

p = sys.argv[1]
with open(p) as f:
    d = json.load(f)
out = d["rollout"]["output"]
print("output keys:", list(out.keys()))
for k, v in out.items():
    if k in ("agent",):
        continue
    s = json.dumps(v)
    print("==", k, "len", len(s), "==")
    print(s[:500])
