"""For PASSING django tasks, how did runtests.py work? They all said ModuleNotFoundError for django in FAILING ones."""
import json
from pathlib import Path

for path in sorted(Path("trajectories").glob("django*.json")):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    tid = d["score"]["task_id"]
    reward = d["score"]["reward"]
    tr = (d.get("rollout") or {}).get("trace") or {}
    for s in tr.get("steps") or []:
        for tc in (s.get("tool_calls") or []):
            cmd = ((tc.get("arguments") or {}).get("command") or "")
            if "runtests" not in cmd:
                continue
            obs = s.get("observation") or {}
            res = obs.get("results") or []
            content = res[0].get("content", "") if res else ""
            try:
                cj = json.loads(content)
                out = (cj.get("output") or "")
            except Exception:
                out = content
            cmd1 = " ".join(cmd.split())[:110]
            out1 = " ".join(out.split())[:200]
            print(f"### {tid} r={reward} CMD: {cmd1}")
            print(f"    OUT: {out1}")
