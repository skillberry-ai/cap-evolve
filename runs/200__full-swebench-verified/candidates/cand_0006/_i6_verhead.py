import json, os, re

TRAJ = './trajectories'

def get_meta(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    return ((d.get("rollout") or {}).get("metadata")) or {}

tasks = [
    "django__django-16667", "astropy__astropy-13453", "django__django-12325",
    "django__django-10554", "django__django-11555", "django__django-12708",
    "django__django-14007", "django__django-14376", "django__django-15629",
    "django__django-16032",
]

# Find the beginning of verifier stdout — look for the git checkout / test patch application section
for task in tasks:
    meta = get_meta(task)
    vs = meta.get("verifier_stdout") or ""
    # The head of verifier stdout should show the 'git diff' extraction or model patch application
    print("=" * 100)
    print(f"### {task}  FIRST 1200 chars of verifier_stdout:")
    print(vs[:1200])
