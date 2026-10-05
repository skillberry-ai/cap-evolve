import json
d = json.load(open("trajectories/sympy__sympy-21612__seed__t0.json"))
steps = d["rollout"]["trace"]["steps"]
for s in steps:
    sid = s.get("step_id")
    if sid in (19, 20, 27, 28, 30):
        print(f"\n===== step {sid} =====")
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command") or ""
            obs = tc.get("observation")
            print("CMD:", cmd[:140])
            print("OBS:", json.dumps(obs)[:1200] if obs else None)
