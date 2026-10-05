import json
d = json.load(open("trajectories/django__django-14007__seed__t0.json"))
tr = d["rollout"]["trace"]
steps = tr.get("steps") or []
print("total steps:", len(steps))
for s in steps[-6:]:
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
        print(f"\n===== [{s.get('step_id')}] CMD: {' '.join(cmd.split())[:200]}")
        print(out[:1200])
    if s.get("source") == "agent" and (s.get("message") or "").strip():
        print("MSG:", s["message"][:500])
