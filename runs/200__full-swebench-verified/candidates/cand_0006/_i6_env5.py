import json, os, re

TRAJ = './trajectories'

def get_rollout(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    return d.get("rollout") or {}

# Where does the verifier's python live? Look in verifier_stdout tracebacks
paths = {}
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith(".json"):
        continue
    task = fn.replace("__cand_0002__t0.json", "")
    meta = (get_rollout(task).get("metadata")) or {}
    vs = meta.get("verifier_stdout") or ""
    for m in re.finditer(r"(/opt/miniconda3/envs/[^\s'\"]*)", vs):
        p = m.group(1).split("/lib/")[0]
        paths.setdefault(p, []).append(task)
    for m in re.finditer(r"python(3\.\d+)", vs):
        paths.setdefault(f"python{m.group(1)}", []).append(task)

for p, tasks in sorted(paths.items()):
    print(f"{p}  <- {len(tasks)} tasks")
    for t in tasks[:4]:
        print(f"    {t}")
