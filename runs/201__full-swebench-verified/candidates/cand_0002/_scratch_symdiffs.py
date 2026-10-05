"""Print the final diffs of failing sympy tasks 17139, 18211 and passing 12096, 13480 for quality comparison."""
import json
from pathlib import Path

WANT = ["sympy__sympy-17139", "sympy__sympy-18211", "sympy__sympy-12096", "sympy__sympy-13480"]
for path in sorted(Path("trajectories").glob("*.json")):
    try:
        d = json.load(open(path))
    except Exception:
        continue
    tid = d["score"]["task_id"]
    if tid not in WANT:
        continue
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
    print(f"\n######## {tid} r={d['score']['reward']}")
    print(last_diff[:2000])
