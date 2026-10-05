"""How do PASSING tasks verify their fixes? Extract their last verify steps."""
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
    # tests-related commands in the second half
    test_cmds = [c for c in cmds if any(k in c for k in ("pytest", "runtests", "bin/test", "tox", "unittest", "python -m"))]
    print(f"\n### {tid} (reward={reward}) n_cmds={len(cmds)} test_cmds={len(test_cmds)}")
    for c in test_cmds[-4:]:
        print("   ", c[:130])
