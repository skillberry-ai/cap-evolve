import json, os, sys

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# What does the harness use as the "model patch"? Check: does the verifier contain
# 'git add -A' / 'git diff'? Look at how the verifier obtains the patch (before pip install).
for task in ["django__django-15863", "astropy__astropy-13453"]:
    d = load(task)
    md = (d.get("rollout") or {}).get("metadata") or {}
    vs = md.get("verifier_stdout", "") or ""
    print("=" * 80)
    print("###", task, "len", len(vs))
    # find 'git diff' or 'git add'
    for marker in ("git add", "git diff", "git log", "git commit", "git status"):
        i = vs.find(marker)
        if i >= 0:
            print(f"[{marker}] ctx: ...{vs[max(0,i-200):i+200]}...")
