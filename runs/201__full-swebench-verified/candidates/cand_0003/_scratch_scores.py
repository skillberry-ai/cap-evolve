import json, os

td = "trajectories"
rows = []
for fn in sorted(os.listdir(td)):
    if not fn.endswith(".json"):
        continue
    with open(os.path.join(td, fn)) as f:
        d = json.load(f)
    task = fn.replace("__seed__t0.json", "")
    sc = d.get("score") or {}
    rw = sc.get("reward")
    fb = (sc.get("feedback") or "")[:80]
    rows.append((rw if rw is not None else -1, task, fb))
rows.sort()
for rw, task, fb in rows:
    print(f"{rw!r:6}  {task:42}  {fb}")
