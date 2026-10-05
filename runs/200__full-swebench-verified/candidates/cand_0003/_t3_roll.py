import json, sys

p = sys.argv[1]
with open(p) as f:
    d = json.load(f)
r = d["rollout"]
print("task_id:", r.get("task_id"))
print("error:", str(r.get("error"))[:500])
print("cost:", r.get("cost_usd"))
print("tokens:", r.get("tokens"))
print("tool_calls:", len(r.get("tool_calls") or []))
tr = r.get("trace")
print("trace type:", type(tr), "len:", len(tr) if hasattr(tr, "__len__") else "n/a")
if isinstance(tr, list) and tr:
    print("first trace item type:", type(tr[0]))
    if isinstance(tr[0], dict):
        print("first item keys:", list(tr[0].keys()))
        print(json.dumps(tr[0], indent=1)[:1500])
elif isinstance(tr, dict):
    print("trace keys:", list(tr.keys()))
    for k, v in tr.items():
        print("  ", k, type(v), (len(v) if hasattr(v, "__len__") else ""))
s = d["score"]
print("reward:", s.get("reward"), "n:", s.get("n"))
print("feedback:", str(s.get("feedback"))[:800])
print("trial_rewards:", s.get("trial_rewards"))
