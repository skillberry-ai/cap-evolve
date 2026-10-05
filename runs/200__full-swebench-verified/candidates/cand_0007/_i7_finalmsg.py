import json, os

TRAJ = "trajectories"
FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]
for t in FAILING:
    d = json.load(open(os.path.join(TRAJ, f"{t}__cand_0002__t0.json")))
    steps = d["rollout"]["output"]["steps"]
    msgs = [s.get("message") for s in steps if s.get("source") == "agent" and s.get("message")]
    final = msgs[-1] if msgs else ""
    print("##", t)
    print("   ", (final or "(empty)")[:600].replace("\n", " | "))
