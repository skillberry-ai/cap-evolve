import json, os, glob

TRAJ = "trajectories"
rows = []
for p in sorted(glob.glob(os.path.join(TRAJ, "*.json"))):
    base = os.path.basename(p)
    task = base.rsplit("__", 2)[0]
    d = json.load(open(p))
    r = d.get("score", {}).get("reward")
    fb = d.get("score", {}).get("feedback", "")
    rows.append((r if r is not None else -1, task, fb[:70]))

rows.sort()
for r, t, fb in rows:
    print(f"{t:48s} r={r:.2f} {fb}")
