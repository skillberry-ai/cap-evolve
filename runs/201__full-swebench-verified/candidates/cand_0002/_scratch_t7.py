import json
d = json.load(open("trajectories/sympy__sympy-21612__seed__t0.json"))
steps = d["rollout"]["trace"]["steps"]
for s in steps:
    sid = s.get("step_id")
    obs = s.get("observation") or {}
    res = obs.get("results") or []
    content = res[0].get("content", "") if res else ""
    for tc in (s.get("tool_calls") or []):
        cmd = (tc.get("arguments") or {}).get("command") or ""
        if any(k in cmd for k in ("verify-fix", "pytest", "bin/test", "pip install", "runtests")):
            out = ""
            try:
                cj = json.loads(content)
                inner = cj.get("output") or ""
                out = inner
            except Exception:
                out = content
            print(f"\n##### step {sid} CMD: {cmd[:160]}")
            print(out[:2500])
