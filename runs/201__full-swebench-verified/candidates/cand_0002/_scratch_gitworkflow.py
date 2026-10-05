"""Check git workflow of failing tasks: did they commit? What does final state look like? Check the LAST few commands."""
import json
from pathlib import Path

for path in sorted(Path("trajectories").glob("*.json")):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    tid = d["score"]["task_id"]
    reward = d["score"]["reward"]
    if reward >= 0.5 or not tid.startswith("django"):
        continue
    tr = (d.get("rollout") or {}).get("trace") or {}
    cmds = []
    for s in tr.get("steps") or []:
        for tc in (s.get("tool_calls") or []):
            cmd = " ".join(((tc.get("arguments") or {}).get("command") or "").split())
            if cmd:
                cmds.append(cmd)
    git_cmds = [c for c in cmds if c.startswith("git ")]
    print(f"\n### {tid} r={reward}")
    for c in git_cmds:
        print("   ", c[:120])
