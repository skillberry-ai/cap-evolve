import json, sys

tasks = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]
for task in tasks:
    d = json.load(open(f"trajectories/{task}__cand_0002__t0.json"))
    ro = d.get("rollout") or {}
    meta = ro.get("metadata") or {}
    vs = meta.get("verifier_stdout", "") or ""
    # Extract the FAIL/ERROR section
    lines = vs.splitlines()
    interesting = []
    grab = False
    for ln in lines:
        if ("FAIL:" in ln or "ERROR:" in ln or "FAILED" in ln or "PASSED" in ln
                or "AssertionError" in ln or "SWEBench results" in ln
                or "Traceback" in ln or ln.startswith("E   ") or "error:" in ln.lower()):
            interesting.append(ln)
    print(f"\n########## {task} ##########")
    for ln in interesting[:40]:
        print("   ", ln[:220])
