"""How do PASSING tasks that reference /opt/miniconda3/envs use it? Show the cmds."""
import glob
import json
import re

for f in sorted(glob.glob("trajectories/*.json")):
    d = json.load(open(f))
    tid = d["rollout"]["task_id"]
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    if not steps:
        continue
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in s.get("tool_calls") or []:
            cmd = (tc.get("arguments") or {}).get("command", "")
            if "envs/testbed" in cmd or "conda activate" in cmd:
                obs = ""
                for r in (s.get("observation") or {}).get("results") or []:
                    c = r.get("content", "")
                    try:
                        j = json.loads(c)
                        obs = (j.get("output") or "").strip().replace("\n", " | ")[:200]
                    except Exception:
                        obs = c[:150]
                print(f"[{tid}] [{s.get('step_id')}] {cmd[:250]}")
                print(f"    -> {obs[:180]}")
