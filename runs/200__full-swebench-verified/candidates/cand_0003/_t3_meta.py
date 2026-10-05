import json, sys

p = sys.argv[1]
with open(p) as f:
    d = json.load(f)
r = d["rollout"]
md = r.get("metadata") or {}
print("metadata keys:", list(md.keys())[:40])
for k, v in md.items():
    s = json.dumps(v) if not isinstance(v, str) else v
    print(f"--- {k} ---")
    print(s[:1200])
    print()
out = r.get("output")
print("output type:", type(out))
if isinstance(out, str):
    print(out[:3000])
elif isinstance(out, dict):
    print("output keys:", list(out.keys()))
    print(json.dumps(out, indent=1)[:3000])
