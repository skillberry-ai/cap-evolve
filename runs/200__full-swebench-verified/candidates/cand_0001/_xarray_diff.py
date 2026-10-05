import json, os, sys

TRAJ = "trajectories"
# For xarray-6992, show the diff the agent produced (last git diff output)
t = "pydata__xarray-6992"
d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
steps = (d["rollout"].get("trace") or {}).get("steps") or []
for s in steps:
    if s.get("source") != "agent":
        continue
    for tc in (s.get("tool_calls") or []):
        cmd = (tc.get("arguments") or {}).get("command", "")
        if "git" in cmd and "diff" in cmd:
            obs = ""
            if s.get("observation"):
                try:
                    c = s["observation"]["results"][0]["content"]
                    j = json.loads(c)
                    obs = j.get("output", "")
                except Exception:
                    pass
            print("CMD:", cmd[:150])
            print("OBS:", obs[:2500])
            print("---")
