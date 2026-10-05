import json, sys
p = sys.argv[1]
idx = int(sys.argv[2])
d = json.load(open(p))
steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
s = steps[idx]
for tc in (s.get("tool_calls") or []):
    print("CMD:")
    print(tc.get("arguments", {}).get("command", ""))
    print()
obs = s.get("observation") or {}
try:
    c = obs["results"][0]["content"]
    j = json.loads(c)
    print("RC:", j.get("returncode"))
    print("OUTPUT:", (j.get("output") or "")[:1500])
except Exception as e:
    print("obs parse err", e)
