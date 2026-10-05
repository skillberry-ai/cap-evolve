import json, os
TRAJ = "trajectories"
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith("cand_0002__t0.json"):
        continue
    task = fn.replace("__cand_0002__t0.json", "")
    d = json.load(open(os.path.join(TRAJ, fn)))
    reward = (d.get("score") or {}).get("reward")
    meta = ((d.get("rollout") or {}).get("metadata")) or {}
    vs = meta.get("verifier_stdout", "") or ""
    print(f"{task:45s} r={reward} vlen={len(vs)}")
    if reward == 0:
        lines = vs.splitlines()
        # find meaningful lines
        for i, l in enumerate(lines):
            if any(k in l for k in ("FAILED", "ERROR", "error", "Traceback", "PASS", "FAIL", "exit", "Exit")):
                print("   ", l[:180])
        print()
