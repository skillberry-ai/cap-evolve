import json, os, sys
TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

def cmds(task):
    d = load(task)
    out = (d.get("rollout") or {}).get("output") or {}
    steps = out.get("steps") or []
    res = []
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            res.append((i, (tc.get("arguments") or {}).get("command", "")))
    return res

task = sys.argv[1]
for i, c in cmds(task):
    print(f"[{i:3d}] {c[:230]}")
