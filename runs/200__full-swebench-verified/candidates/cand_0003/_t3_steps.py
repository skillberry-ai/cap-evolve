import json, sys

p = sys.argv[1]
maxn = int(sys.argv[2]) if len(sys.argv) > 2 else 10
with open(p) as f:
    d = json.load(f)
tr = d["rollout"]["trace"]
steps = tr["steps"]
print("N steps:", len(steps))
print("agent:", json.dumps(tr.get("agent"))[:300])
print("notes:", tr.get("notes"))
print("final_metrics:", json.dumps(tr.get("final_metrics"))[:400])
print("=" * 80)
for i, s in enumerate(steps[:maxn]):
    if not isinstance(s, dict):
        print(i, type(s), str(s)[:200])
        continue
    print(f"--- step {i} keys={list(s.keys())}")
    for k, v in s.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            print(f"   {k} = {str(v)[:400]}")
        else:
            print(f"   {k} : {type(v).__name__} {str(v)[:300]}")
