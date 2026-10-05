import json
d = json.load(open("trajectories/django__django-14007__seed__t0.json"))
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
        cmd1 = " ".join(cmd.split())
        print(f"\n===== [{s.get('step_id')}] CMD: {cmd1[:220]}")
        print((out[:800] if out.strip() else "(empty)"))
