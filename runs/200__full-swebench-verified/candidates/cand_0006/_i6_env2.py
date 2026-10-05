import json, os

TRAJ = './trajectories'

def get_rollout(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    return d.get("rollout") or {}

# Look at the first observation(s) of each task: what does `ls -la` show?
# This tells us the working directory structure of the eval environment.
task = "django__django-16667"
ro = get_rollout(task)
steps = ((ro.get("trace") or {}).get("steps")) or []
for i, s in enumerate(steps[:6]):
    if s.get("source") == "agent":
        obs = s.get("observation")
        if obs:
            try:
                j = json.loads(obs.get("results")[0].get("content"))
                print(f"[{i}] rc={j.get('returncode')}")
                print((j.get("output") or "")[:2500])
            except Exception:
                print(str(obs)[:1000])
        print("~~~")
