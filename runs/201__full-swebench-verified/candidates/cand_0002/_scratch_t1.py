import json
d = json.load(open("trajectories/sympy__sympy-21612__seed__t0.json"))
steps = d["rollout"]["trace"]["steps"]
for s in steps:
    for tc in s.get("tool_calls") or []:
        cmd = (tc.get("arguments") or {}).get("command") or ""
        if "pytest" in cmd or "verify-fix" in cmd or "bin/test" in cmd:
            obs = tc.get("observation") or {}
            res = obs.get("results") or []
            content = res[0].get("content", "") if res else "(NO RESULTS)"
            print(f"### step {s.get('step_id')} CMD: {cmd[:150]}")
            print(content[:1800])
            print("---")
