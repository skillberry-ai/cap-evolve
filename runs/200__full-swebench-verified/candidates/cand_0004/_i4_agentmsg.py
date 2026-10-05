import json, os
TRAJ = "trajectories"
fn = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(fn))
out = d.get("rollout", {}).get("output") or {}
steps = out.get("steps") or []
# print first 3 steps structure
for s in steps[:6]:
    src = s.get("source")
    msg = s.get("message") or ""
    tcs = s.get("tool_calls")
    print(f"--- source={src} len={len(msg)} tool_calls={'yes' if tcs else 'no'}")
    if tcs:
        for tc in tcs[:2]:
            print("   TOOL:", json.dumps(tc)[:300])
    else:
        print("   MSG:", repr(msg[:200]))
