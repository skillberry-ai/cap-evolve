import json, sys
p = sys.argv[1]
d = json.load(open(p))
steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
needle = sys.argv[2] if len(sys.argv) > 2 else "git apply"
for idx, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    for tc in (s.get("tool_calls") or []):
        cmd = (tc.get("arguments") or {}).get("command", "")
        if needle in cmd:
            print("#" * 30, "IDX", idx)
            print(cmd[:3000])
            obs = s.get("observation") or {}
            try:
                c = obs["results"][0]["content"]
                j = json.loads(c)
                print("RC:", j.get("returncode"))
                print("OUT:", (j.get("output") or "")[:600])
            except Exception:
                pass
            print()
