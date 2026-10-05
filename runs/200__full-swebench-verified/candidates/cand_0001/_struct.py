import json, os, sys

TRAJ = "trajectories"

data = json.load(open(os.path.join(TRAJ, "django__django-10554__seed__t0.json")))
print("TOP KEYS:", list(data.keys()))
r = data["rollout"]
print("ROLLOUT KEYS:", list(r.keys()))
tr = r.get("trace") or {}
print("TRACE KEYS:", list(tr.keys()))
steps = tr.get("steps") or []
for s in steps[:4]:
    print("---- step", s.get("step_id"), "source:", s.get("source"))
    for k, v in s.items():
        if k in ("step_id",):
            continue
        vs = json.dumps(v)
        print(f"  {k}: {vs[:1500]}")
