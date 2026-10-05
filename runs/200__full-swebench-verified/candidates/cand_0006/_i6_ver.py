import json, os

TRAJ = './trajectories'

# Check what the harness sees as the final patch: look at verifier stdout for
# 'Updated N paths' lines and which paths. Also look for what tests were run by the verifier.
def get_meta(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    return ((d.get("rollout") or {}).get("metadata")) or {}

tasks = [
    "django__django-16667", "astropy__astropy-13453", "django__django-12325",
    "django__django-10554", "django__django-11555",
]

for task in tasks:
    meta = get_meta(task)
    vs = meta.get("verifier_stdout") or ""
    # find "Updated N paths from <sha>" lines
    import re
    ups = re.findall(r"Updated (\d+) paths? from (\w+)", vs)
    print(f"### {task}: updated-paths lines={ups}")
    # Look for test command lines the verifier ran
    lines = vs.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith("+ git checkout") or "python -m pytest" in ln or "runtests" in ln:
            print(f"    verifier: {ln[:160]}")
