import json, os, glob

TRAJ = "trajectories"
rows = []
for fn in sorted(glob.glob(os.path.join(TRAJ, "*.json"))):
    task = os.path.basename(fn).replace("__cand_0002__t0.json", "")
    d = json.load(open(fn))
    score = (d.get("score") or {})
    reward = score.get("reward")
    ro = d.get("rollout") or {}
    steps = ((ro.get("output") or {}).get("steps")) or []
    msgs = [s for s in steps if s.get("source") in ("agent", "user")]
    n_steps = sum(1 for s in steps if s.get("source") == "agent")
    rows.append((task, reward, n_steps, len(steps)))

rows.sort(key=lambda r: (r[1] if r[1] is not None else -1, r[0]))
print(f"{'task':45s} {'reward':>6s} {'agent_steps':>11s} {'total':>5s}")
for t, r, ns, tot in rows:
    print(f"{t:45s} {str(r):>6s} {ns:>11d} {tot:>5d}")
