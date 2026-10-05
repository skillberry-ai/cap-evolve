"""Check what the final patch output looked like for failing vs passing tasks.

Specifically: did the agent produce the final diff by 'git diff HEAD~1' (works only if
it committed) or 'git diff' (works only if NOT committed)?
"""
import glob
import json
import re

for f in sorted(glob.glob("trajectories/*.json")):
    d = json.load(open(f))
    r = d["rollout"]
    tr = r.get("trace") or {}
    steps = tr.get("steps") or []
    rew = d["score"].get("reward") or 0
    name = f.split("/")[-1].split("__seed")[0]
    committed = False
    diff_cmd = None
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in s.get("tool_calls") or []:
            cmd = (tc.get("arguments") or {}).get("command", "")
            if re.search(r"git (add|commit)\b", cmd):
                committed = True
            m = re.search(r"git\s+(--no-pager\s+)?diff\s+(\S+)", cmd)
            if m and "HEAD" in cmd:
                diff_cmd = cmd[:60]
    cat = "PASS" if rew >= 0.5 else "FAIL"
    print(f"{cat} {name:<44} committed={committed!s:<5} lastdiff={diff_cmd!r}")
