"""Check git workflow of PASSING tasks: do they commit?"""
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
    cmds = []
    for s in tr.get("steps") or []:
        for tc in (s.get("tool_calls") or []):
            cmd = " ".join(((tc.get("arguments") or {}).get("command") or "").split())
            if cmd:
                cmds.append(cmd)
    commits = [c for c in cmds if "git commit" in c or "git add" in c]
    print(f"{tid} r={reward} commits={len(commits)}")
