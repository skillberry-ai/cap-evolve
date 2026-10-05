import json, os, glob

TRAJ = "trajectories"

FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]

def obs_of(s):
    obs, rc = "", None
    if s.get("observation"):
        try:
            c = s["observation"]["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output", "")
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc

for t in FAILING:
    p = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    d = json.load(open(p))
    steps = d["rollout"]["output"]["steps"]
    vs = d["rollout"]["metadata"].get("verifier_stdout", "")
    print("=" * 100)
    print("##", t)
    # Show the tail of verifier stdout (the actual test results)
    tail = vs[-1200:]
    print("--- verifier tail ---")
    print(tail)
