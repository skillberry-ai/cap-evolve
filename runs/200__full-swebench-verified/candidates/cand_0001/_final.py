import json, os, sys

TRAJ = "trajectories"

data = json.load(open(os.path.join(TRAJ, "django__django-10554__seed__t0.json")))
r = data["rollout"]
tr = r.get("trace") or {}
steps = tr.get("steps") or []
# final agent message and output
out = r.get("output")
print("=== ROLLOUT.OUTPUT type:", type(out))
print(json.dumps(out)[:2000] if out else "(None)")
print()
print("=== LAST STEPS ===")
for s in steps[-6:]:
    print("---- step", s.get("step_id"), "source:", s.get("source"))
    for k in ("message", "reasoning_content"):
        v = s.get(k)
        if v:
            print(f"  {k}: {v[:1500]}")
    tcs = s.get("tool_calls")
    if tcs:
        for tc in tcs:
            print("  TOOL:", tc.get("function_name"), json.dumps(tc.get("arguments"))[:1500])
