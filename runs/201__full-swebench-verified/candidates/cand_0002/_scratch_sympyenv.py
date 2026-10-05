"""Did sympy tasks (which fail on missing mpmath) have a conda env with sympy deps? Check what sympy-24213 (PASSING) did."""
import json
d = json.load(open("trajectories/sympy__sympy-24213__seed__t0.json"))
tr = d["rollout"]["trace"]
for s in tr.get("steps") or []:
    for tc in (s.get("tool_calls") or []):
        cmd = ((tc.get("arguments") or {}).get("command") or "")
        obs = s.get("observation") or {}
        res = obs.get("results") or []
        content = res[0].get("content", "") if res else ""
        try:
            cj = json.loads(content)
            out = cj.get("output") or ""
        except Exception:
            out = content
        print(f"\n===== [{s.get('step_id')}] CMD: {' '.join(cmd.split())[:170]}")
        print((out[:600] if out.strip() else "(empty)"))
