import json, os, sys

TRAJ = 'trajectories'

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + '__'):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667",
]

def obs_of(s):
    if not s.get("observation"):
        return "", None
    try:
        c = s["observation"]["results"][0]["content"]
        j = json.loads(c)
        return j.get("output", "") or "", j.get("returncode")
    except Exception:
        return "", None

for task in FAILING:
    d = load(task)
    meta = ((d.get('rollout') or {}).get('metadata')) or {}
    vs = meta.get('verifier_stdout', '') or ''
    print("=" * 100)
    print("TASK", task)
    # last ~40 lines of verifier stdout
    lines = vs.splitlines()
    print(f"verifier_stdout: {len(lines)} lines; last 35:")
    for l in lines[-35:]:
        print("  |", l[:200])
