"""Check how sessions END for all tasks: submitted vs step-limit vs stall (optimizer scratch)."""
import json
from pathlib import Path

for path in sorted(Path("trajectories").glob("*.json")):
    try:
        with open(path) as f:
            d = json.load(f)
    except Exception as e:
        print(f"{path.name:52s} LOAD ERROR {e}")
        continue
    score = d["score"]
    ro = d.get("rollout") or {}
    tr = ro.get("trace") or {}
    steps = tr.get("steps") or []
    cfg = ((ro.get("output") or {}).get("agent") or {}).get("extra", {}).get("agent_config") or {}
    fm = (ro.get("output") or {}).get("final_metrics") or {}
    total = fm.get("total_steps")
    last_cmds = []
    for s in steps[-3:]:
        for tc in s.get("tool_calls") or []:
            last_cmds.append(((tc.get("arguments") or {}).get("command") or "")[:60])
    submitted = any("COMPLETE_TASK" in c for c in last_cmds)
    err = ro.get("error")
    nsteps = len(steps)
    print(f"{score['task_id']:48s} reward={score['reward']:.2f} steps={nsteps} submitted={submitted} last={(last_cmds[-1] if last_cmds else '?')!r}")
