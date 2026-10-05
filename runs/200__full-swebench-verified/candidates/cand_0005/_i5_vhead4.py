import json, os, sys

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

d = load("django__django-15863")
md = (d.get("rollout") or {}).get("metadata") or {}
vs = md.get("verifier_stdout", "") or ""
# search for the python invocation of the runner in the whole stdout
for marker in ("python", "runtests", "tox"):
    i = 0
    count = 0
    while count < 6:
        i = vs.find(marker, i)
        if i < 0:
            break
        seg = vs[max(0, i - 120):i + 120].replace("\n", " | ")
        print(f"[{marker}] ...{seg}...")
        i += 1
        count += 1
    print()
