"""Check what patch the failing django tasks produced: look at their final git diff/show commands and outputs."""
import json
from pathlib import Path

TASKS = ["django__django-10554", "django__django-12325", "django__django-14376", "django__django-15629", "django__django-16667"]
for path in sorted(Path("trajectories").glob("*.json")):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    tid = d["score"]["task_id"]
    if tid not in TASKS:
        continue
    tr = (d.get("rollout") or {}).get("trace") or {}
    for s in tr.get("steps") or []:
        for tc in (s.get("tool_calls") or []):
            cmd = ((tc.get("arguments") or {}).get("command") or "")
            if "git diff" in cmd or "git show" in cmd or "git status" in cmd or "git log" in cmd:
                obs = s.get("observation") or {}
                res = obs.get("results") or []
                content = res[0].get("content", "") if res else ""
                try:
                    cj = json.loads(content)
                    out = (cj.get("output") or "")
                except Exception:
                    out = content
                cmd1 = " ".join(cmd.split())[:110]
                out1 = " ".join(out.split())[:400]
                print(f"### {tid} [{s.get('step_id')}] CMD: {cmd1}")
                print(f"    OUT: {out1}")
