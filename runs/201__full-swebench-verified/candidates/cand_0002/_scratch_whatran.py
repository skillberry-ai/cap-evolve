"""Understand what actually got evaluated: look for the patch in the trace for a specific failing task (django-14376 which has clear small diff) and check if the fix LOOKS correct."""
import json
d = json.load(open("trajectories/django__django-14376__seed__t0.json"))
tr = d["rollout"]["trace"]
for s in tr["steps"]:
    for tc in (s.get("tool_calls") or []):
        cmd = ((tc.get("arguments") or {}).get("command") or "")
        if "diff" in cmd:
            obs = s.get("observation") or {}
            res = obs.get("results") or []
            content = res[0].get("content", "") if res else ""
            try:
                cj = json.loads(content)
                out = (cj.get("output") or "")
            except Exception:
                out = content
            print("CMD:", cmd[:150])
            print("OUT:", out[:3000])
            print("=" * 60)
