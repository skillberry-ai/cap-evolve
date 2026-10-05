"""Summarize all trajectories: task, reward, #steps, and key info."""
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
    steps = tr.get("steps") or []
    rows.append((os.path.basename(f).split("__seed")[0],
                 sc.get("reward"), len(steps), tr.get("final_metrics")))
for name, rew, n, fm in rows:
    print(f"{rew!r:>6}  steps={n:>3}  fm={json.dumps(fm)[:120]}  {name}")
