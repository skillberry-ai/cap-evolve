import json, os
TRAJ = "trajectories"
def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None
def steps_of(task):
    d = load(task)
    out = (d.get("rollout") or {}).get("output") or {}
    return out.get("steps") or []
steps = steps_of("django__django-16667")
# inspect the raw observation JSON for step 20
s = steps[20]
obs = s.get("observation")
print(json.dumps(obs, indent=1)[:2000])
