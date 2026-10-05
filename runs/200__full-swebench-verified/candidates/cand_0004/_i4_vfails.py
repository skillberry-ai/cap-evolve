import json, os
TRAJ = "trajectories"
FAIL = ["astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667"]
for task in FAIL:
    for fn in sorted(os.listdir(TRAJ)):
        if fn.startswith(task + "__"):
            break
    d = json.load(open(os.path.join(TRAJ, fn)))
    meta = ((d.get("rollout") or {}).get("metadata")) or {}
    vs = meta.get("verifier_stdout", "") or ""
    print("="*100)
    print(task)
    print(vs[-3000:])
