"""Full digest of django-12325: every command with output."""
import json
d = json.load(open("trajectories/django__django-12325__seed__t0.json"))
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
        print(f"\n===== [{s.get('step_id')}] CMD: {cmd1[:250]}")
        out1 = out[:1200]
        print(out1 if out1.strip() else "(empty)")
