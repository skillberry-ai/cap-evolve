import json, os, re

TRAJ = "trajectories"

# Understand the verifier's test command for each failing task by looking at
# the head of verifier_stdout where the harness runs tests.
FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]

for t in FAILING:
    p = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    d = json.load(open(p))
    vs = d["rollout"]["metadata"].get("verifier_stdout", "")
    # The verifier output often shows the applied test patch and then a run command
    # Look for lines with 'python' or 'runtests' or 'conda' etc.
    lines = vs.splitlines()
    print("#" * 80)
    print("##", t, "verifier len", len(vs))
    for i, l in enumerate(lines[:40]):
        print("   ", l[:160])
