import json, os

TRAJ = './trajectories'

def get_rollout(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    return d.get("rollout") or {}

# Gather python interpreter paths referenced in OBSERVATIONS (tracebacks show sys.path)
import re
paths = {}
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith(".json"):
        continue
    task = fn.replace("__cand_0002__t0.json", "")
    ro = get_rollout(task)
    steps = ((ro.get("trace") or {}).get("steps")) or []
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        obs = s.get("observation")
        if not obs:
            continue
        try:
            j = json.loads(obs.get("results")[0].get("content"))
        except Exception:
            continue
        out = (j.get("output") or "") + (j.get("output_head") or "")
        for m in re.finditer(r"(/opt/[^\s'\"]*python[\d.]*)", out):
            p = m.group(1)
            paths.setdefault(p, []).append(task)

for p, tasks in sorted(paths.items()):
    print(f"{p}  <- {len(tasks)} tasks, e.g. {tasks[:3]}")
