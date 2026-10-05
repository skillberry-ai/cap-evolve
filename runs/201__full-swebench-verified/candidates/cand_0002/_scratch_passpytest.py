"""For passing tasks: extract pytest output - did they run successfully?"""
import json
from pathlib import Path

for path in sorted(Path("trajectories").glob("*.json")):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    tid = d["score"]["task_id"]
    reward = d["score"]["reward"]
    if reward < 0.5:
        continue
    tr = (d.get("rollout") or {}).get("trace") or {}
    for s in tr.get("steps") or []:
        for tc in (s.get("tool_calls") or []):
            cmd = ((tc.get("arguments") or {}).get("command") or "")
            if "pytest" not in cmd:
                continue
            obs = s.get("observation") or {}
            res = obs.get("results") or []
            content = res[0].get("content", "") if res else ""
            try:
                cj = json.loads(content)
                out = (cj.get("output") or "")
                rc = cj.get("returncode")
            except Exception:
                out, rc = content, "?"
            cmd1 = " ".join(cmd.split())[:100]
            out1 = " ".join(out.split())[:200]
            print(f"### {tid} rc={rc} CMD: {cmd1}")
            print(f"    OUT: {out1}")
