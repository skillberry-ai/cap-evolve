import json, os

TRAJ = "trajectories"
# What test command did the VERIFIER run? Extract the exact command from verifier
# stdout: it usually echoes the script. Search for the runtests invocation.

for t in ["django__django-16667", "django__django-11555", "django__django-12325",
          "django__django-12708", "django__django-14007", "django__django-14376",
          "django__django-15629", "django__django-16032", "django__django-10554"]:
    p = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    d = json.load(open(p))
    vs = d["rollout"]["metadata"].get("verifier_stdout", "") or ""
    ve = d["rollout"]["metadata"].get("verifier_stderr", "") or ""
    print("#" * 80)
    print("##", t)
    # Look for command lines in stderr (set -x output)
    for line in ve.splitlines():
        if any(m in line for m in ("runtests", "python", "git apply", "git checkout", "test_patch")):
            print("  ERR:", line[:200])
