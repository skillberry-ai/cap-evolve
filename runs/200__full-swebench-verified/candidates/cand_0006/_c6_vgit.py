import json, glob, os

# Check the verifier flow: does it reset the working tree before applying test patch?
# Look for 'git checkout' / 'git reset' patterns in verifier stdout for all failing tasks.
FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]
for task in FAILING:
    d = json.load(open(f"trajectories/{task}__cand_0002__t0.json"))
    ro = d.get("rollout") or {}
    meta = ro.get("metadata") or {}
    vs = meta.get("verifier_stdout", "") or ""
    vse = meta.get("verifier_stderr", "") or ""
    print(f"\n########## {task} (stdout {len(vs)}, stderr {len(vse)}) ##########")
    if vse:
        print("STDERR head:", vse[:400])
    # find lines with git
    for ln in vs.splitlines():
        if ln.startswith("+") or ln.strip().startswith("git"):
            print("   |", ln.strip()[:200])
