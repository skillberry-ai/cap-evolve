"""In 14007, was asgiref importable after pip install? The combined command's output only shows the python part. Let me check the steps right before/after 33."""
import json
d = json.load(open("trajectories/django__django-14007__seed__t0.json"))
tr = d["rollout"]["trace"]
for s in tr.get("steps") or []:
    sid = s.get("step_id")
    if sid in (31, 32, 33, 34, 35, 36):
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
            print(f"\n===== [{sid}] CMD: {' '.join(cmd.split())[:250]}")
            print(out[:1500])
