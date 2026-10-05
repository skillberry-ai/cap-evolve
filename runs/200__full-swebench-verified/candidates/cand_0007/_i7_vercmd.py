import json, sys, os

TRAJ = "trajectories"
# For each failing task, show what the agent's final code state diff was (verifier shows
# "Updated N paths from <commit>"). More useful: find what test command the VERIFIER ran.
# Look at verifier_stdout for the test invocation lines.

TASKS = sys.argv[1:] or [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]
for t in TASKS:
    p = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    d = json.load(open(p))
    vs = d["rollout"]["metadata"].get("verifier_stdout", "") or ""
    print("=" * 90)
    print("##", t)
    lines = vs.splitlines()
    # find lines mentioning test invocation
    for i, ln in enumerate(lines):
        if any(m in ln for m in ("runtests.py", "python -m pytest", "pytest ", "test_patch", "git checkout", "git apply", "conftest")):
            print(f"  [{i}] {ln[:220]}")
