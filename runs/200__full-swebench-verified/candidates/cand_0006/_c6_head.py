import json, sys
p = sys.argv[1]
d = json.load(open(p))
steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
for s in steps[:n]:
    src = s.get("source")
    msg = s.get("message") or ""
    print("=" * 30, "step", s.get("step_id"), "src", src, "=" * 30)
    print(str(msg)[:3000])
    print()
