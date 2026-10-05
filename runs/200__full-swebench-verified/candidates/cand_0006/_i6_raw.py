import json, sys, os

TRAJ = './trajectories'

def get_steps(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    ro = d.get("rollout") or {}
    return ((ro.get("trace") or {}).get("steps")) or []

task = sys.argv[1]
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
hi = int(sys.argv[3]) if len(sys.argv) > 3 else 10**6
steps = get_steps(task)
print(f"TASK {task}: {len(steps)} steps, showing {lo}..{hi}")
for i, s in enumerate(steps):
    if not (lo <= i < hi):
        continue
    print("-" * 90)
    print(f"[{i}] source={s.get('source')}")
    for k in s:
        if k in ("step_id", "source", "message", "tool_calls", "observation"):
            continue
        print(f"    {k}: {str(s[k])[:200]!r}")
    if s.get("message"):
        print(f"    message: {s['message'][:300]!r}")
    if s.get("tool_calls"):
        print(f"    tool_calls: {json.dumps(s['tool_calls'])[:400]!r}")
    if s.get("observation"):
        print(f"    observation: {json.dumps(s['observation'])[:1500]!r}")
