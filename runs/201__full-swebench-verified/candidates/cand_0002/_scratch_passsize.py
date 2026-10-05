"""For each passing sympy task: final diff size (lines)."""
import json
from pathlib import Path
import re

for path in sorted(Path("trajectories").glob("sympy*.json")):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    tid = d["score"]["task_id"]
    reward = d["score"]["reward"]
    tr = (d.get("rollout") or {}).get("trace") or {}
    last_diff = ""
    for s in tr.get("steps") or []:
        for tc in (s.get("tool_calls") or []):
            cmd = ((tc.get("arguments") or {}).get("command") or "")
            if "git" in cmd and ("diff" in cmd or "show" in cmd):
                obs = s.get("observation") or {}
                res = obs.get("results") or []
                content = res[0].get("content", "") if res else ""
                try:
                    cj = json.loads(content)
                    out = cj.get("output") or ""
                except Exception:
                    out = content
                if "diff --git" in out:
                    last_diff = out
    add = len(re.findall(r"^\+", last_diff, re.M))
    rem = len(re.findall(r"^-", last_diff, re.M))
    print(f"{tid} r={reward} diff +/-: {add}/{rem}")
