import json, os

TRAJ = "trajectories"
# Now categorize the failing tasks by the verifier's actual test failure:
# 1. Test ERRORS at setup/collection (env-related, but the verifier's env is fine — these
#    are genuine failures of the FIX), vs
# 2. assertion failures (fix logic wrong).
# Extract the last test-run summary from verifier stdout for each failing task.
FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]
for t in FAILING:
    d = json.load(open(os.path.join(TRAJ, f"{t}__cand_0002__t0.json")))
    vs = d["rollout"]["metadata"].get("verifier_stdout", "")
    # find FAILED lines and summary lines
    fails = [ln for ln in vs.splitlines() if ln.startswith("FAILED") or ln.startswith("ERROR:") or "ERROR:" in ln[:8]]
    summ = [ln for ln in vs.splitlines() if ln.startswith("Ran ") or ("failed" in ln and "passed" in ln) or ln.startswith("FAILED (")]
    print("##", t)
    for f in fails[:6]:
        print("   ", f[:130])
    for s in summ[:3]:
        print("   SUM:", s[:130])
