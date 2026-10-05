import json, sys

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
    lines = vs.splitlines()
    # Find the test command line(s) the verifier used — usually after "git apply" lines
    print(f"\n########## {task} ##########")
    for i, ln in enumerate(lines):
        if ("python -m pytest" in ln or "runtests.py" in ln or "python -m unittest" in ln
                or "python -m django" in ln or "tox " in ln):
            print("   CMD:", ln.strip()[:250])
    # Also find the git apply lines
    for i, ln in enumerate(lines):
        if ln.startswith("+ git apply") or "git checkout" in ln:
            print("   VERIF:", ln.strip()[:250])
