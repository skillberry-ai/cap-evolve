"""Extract final patch (git diff vs task base) evidence from each trace: what files the agent's final diff contains.

Look for the last 'git diff' or 'git show' output, plus commits made during the session.
"""
import glob
import json
import re

for f in sorted(glob.glob("trajectories/*.json")):
    d = json.load(open(f))
    r = d["rollout"] or {}
    tr = r.get("trace") or {}
    steps = tr.get("steps") or []
    tid = r.get("task_id")
    rew = (d.get("score") or {}).get("reward")
    commits = []
    diffs = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in s.get("tool_calls") or []:
            cmd = (tc.get("arguments") or {}).get("command", "")
            m = re.match(r"git commit", cmd.strip())
            if m:
                commits.append(s.get("step_id"))
        obs = ""
        for rr in (s.get("observation") or {}).get("results") or []:
            c = rr.get("content", "")
            try:
                j = json.loads(c)
                obs = (j.get("output") or "")
            except Exception:
                obs = ""
            if "diff --git" in obs:
                files = re.findall(r"diff --git a/(\S+) b/(\S+)", obs)
                diffs.append((s.get("step_id"), [a for a, b in files]))
    print(f"{tid}  rew={rew} commits@{commits} lastdiffs={diffs[-2:]}")
