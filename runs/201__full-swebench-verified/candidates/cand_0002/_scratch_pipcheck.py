"""Which failing tasks tried pip install and did it work?"""
import json
from pathlib import Path

for path in sorted(Path("trajectories").glob("*.json")):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    tid = d["score"]["task_id"]
    reward = d["score"]["reward"]
    tr = (d.get("rollout") or {}).get("trace") or {}
    pip_cmds = 0
    for s in tr.get("steps") or []:
        for tc in (s.get("tool_calls") or []):
            cmd = ((tc.get("arguments") or {}).get("command") or "")
            if "pip install" in cmd:
                pip_cmds += 1
                obs = s.get("observation") or {}
                res = obs.get("results") or []
                content = res[0].get("content", "") if res else ""
                try:
                    cj = json.loads(content)
                    out = cj.get("output") or ""
                except Exception:
                    out = content
                ok = "Successfully installed" in out
                print(f"### {tid} r={reward} pip: {'OK: ' + [l for l in out.splitlines() if 'Successfully' in l][:1].__str__()[:80] if ok else 'FAILED: ' + ' '.join(out.split())[:120]}")
    if not pip_cmds:
        pass
