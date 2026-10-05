import json, sys, os

TRAJ = './trajectories'

def get_steps(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    ro = d.get("rollout") or {}
    return ((ro.get("trace") or {}).get("steps")) or []

def obs_text(s):
    obs = s.get("observation")
    if not obs:
        return None, None
    try:
        c = obs.get("results")[0].get("content")
        j = json.loads(c)
        return j.get("output", ""), j.get("returncode")
    except Exception:
        return str(obs)[:500], None

task = sys.argv[1]
pat = sys.argv[2] if len(sys.argv) > 2 else ""
steps = get_steps(task)
print(f"TASK {task}: {len(steps)} steps")
for i, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    for tc in (s.get("tool_calls") or []):
        cmd = (tc.get("arguments") or {}).get("command") or ""
        if pat and pat not in cmd:
            continue
        # find the following observation step
        out, rc = None, None
        for j in range(i + 1, len(steps)):
            ns = steps[j]
            if ns.get("source") != "agent":
                out, rc = obs_text(ns)
                break
        print("=" * 90)
        print(f"[{i}] CMD: {cmd[:500]}")
        print(f"     rc={rc}")
        if out is not None:
            print(f"     OUT(first 900): {out[:900]!r}")
            if len(out) > 900:
                print(f"     OUT(last 400): {out[-400:]!r}")
