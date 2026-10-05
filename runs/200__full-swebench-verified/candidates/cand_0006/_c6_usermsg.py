import json, sys
p = sys.argv[1]
d = json.load(open(p))
steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
s = steps[1]
msg = s.get("message") or ""
start = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
end = int(sys.argv[3]) if len(sys.argv) > 3 else start + 4000
print(msg[start:end])
