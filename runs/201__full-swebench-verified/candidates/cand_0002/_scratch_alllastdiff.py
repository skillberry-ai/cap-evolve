"""For each failing task, get the FULL final diff the agent produced (git diff HEAD^ HEAD or git show) to judge whether the fix itself was correct."""
import json
from pathlib import Path

for path in sorted(Path("trajectories").glob("*.json")):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    tid = d["score"]["task_id"]
    reward = d["score"]["reward"]
    if reward >= 0.5:
        continue
    tr = (d.get("rollout") or {}).get("trace") or {}
    last_diff = ""
    for s in tr.get("steps") or []:
        for tc in (s.get("tool_calls") or []):
            cmd = ((tc.get("arguments") or {}).get("command") or "")
            if "git diff" in cmd or ("git show" in cmd and "--patch" not in cmd) or "show HEAD" in cmd:
                obs = s.get("observation") or {}
                res = obs.get("results") or []
                content = res[0].get("content", "") if res else ""
                try:
                    cj = json.loads(content)
                    out = (cj.get("output") or "")
                except Exception:
                    out = content
                if "diff --git" in out:
                    last_diff = out
    print(f"\n######## {tid} r={reward}")
    print(last_diff[:1800] if last_diff else "(no diff output seen)")
