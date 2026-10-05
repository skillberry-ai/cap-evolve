import json

with open("_t3_baseline.json") as f:
    b = json.load(f)
v = b["val"]["per_task"]
base = {t["task_id"]: t["reward"] for t in v}

import os
TRAJ = "trajectories"
cur = {}
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith(".json"):
        continue
    task = fn.replace("__cand_0002__t0.json", "")
    d = json.load(open(os.path.join(TRAJ, fn)))
    cur[task] = (d.get("score") or {}).get("reward")

print(f"{'task':44s} {'seed':>6s} {'c2':>6s} {'delta':>6s}")
for t in sorted(base):
    c = cur.get(t)
    d = (c - base[t]) if c is not None else None
    print(f"{t:44s} {base[t]:>6.2f} {c!s:>6s} {d!s:>6s}")
