"""Check what python environments exist per task: search all traces for env discovery commands."""
import glob
import json
import re
import sys

pat = re.compile(r"(conda|/opt/|envs|virtualenv|venv|python3\.\d+|which python|ls /opt)", re.I)
for f in sorted(glob.glob("trajectories/*.json")):
    d = json.load(open(f))
    r = d["rollout"]
    tr = (r.get("trace") or {})
    steps = tr.get("steps") or []
    hits = []
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in s.get("tool_calls") or []:
            cmd = (tc.get("arguments") or {}).get("command", "")
            if pat.search(cmd):
                hits.append((i, cmd[:160]))
    name = f.split("/")[-1].split("__seed")[0]
    rew = d["score"].get("reward")
    if hits:
        print(f"== {name} (reward={rew})")
        for i, h in hits[:6]:
            print(f"   [{i}] {h}")
