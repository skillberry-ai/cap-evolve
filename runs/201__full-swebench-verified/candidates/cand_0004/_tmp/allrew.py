"""Summarize all trajectories: task, reward, #steps, and last few commands."""
import glob
import json
import os

rows = []
for f in sorted(glob.glob("trajectories/*.json")):
    try:
        d = json.load(open(f))
    except Exception as e:
        print("ERR", f, e)
        continue
    sc = d.get("score", {})
    tr = (d.get("rollout") or {}).get("trace") or {}
    rows.append((os.path.basename(f).split("__seed")[0],
                 sc.get("reward"), len(tr.get("steps") or [])))
for name, rew, n in rows:
    print(f"{rew!r:>6}  steps={n:>3}  {name}")
