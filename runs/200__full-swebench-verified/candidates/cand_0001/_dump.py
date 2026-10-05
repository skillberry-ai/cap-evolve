import json, os

TRAJ = "trajectories"
# Compare passing vs failing traces: what does a PASSING task's command flow look like?
t = "django__django-12039"
with open(os.path.join(TRAJ, f"{t}__seed__t0.json")) as fh:
    data = json.load(fh)
r = data["rollout"]
steps = r["trace"]["steps"]
print(f"### {t} reward={data['score']['reward']}")
for s in steps:
    if s["source"] != "agent":
        continue
    for tc in (s.get("tool_calls") or []):
        cmd = (tc.get("arguments") or {}).get("command", "")
        obs = ""
        rc = ""
        if s.get("observation"):
            try:
                c = s["observation"]["results"][0]["content"]
                j = json.loads(c)
                obs = j.get("output", "")
                rc = j.get("returncode", "")
            except Exception:
                pass
        print(f"[{s['step_id']:>3}] rc={rc:>3} | {cmd[:180]}")
        obs_short = obs[:200].replace("\n", " ⏎ ")
        if obs_short:
            print(f"        OUT: {obs_short}")
