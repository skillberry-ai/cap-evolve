import json, os
TRAJ = "trajectories"
def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# Look at verifier_stderr which may contain the harness's setup commands (model patch extraction)
for t in ["django__django-16667", "astropy__astropy-13453"]:
    d = load(t)
    se = ((d.get("rollout") or {}).get("metadata") or {}).get("verifier_stderr", "") or ""
    print("="*80)
    print(t, "stderr len:", len(se))
    print(se[:3000])
