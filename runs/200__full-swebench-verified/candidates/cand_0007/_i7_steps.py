import json, os

TRAJ = "trajectories"
p = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(p))
steps = d["rollout"]["output"]["steps"]
for s in steps[:4]:
    print("STEP", s.get("step_id"), s.get("source"))
    m = s.get("message", "")
    print(m[:2500])
    print("~~~~ENDSTEP~~~~")
