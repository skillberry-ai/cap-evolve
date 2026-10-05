import json, os

TRAJ = './trajectories'

def get_rollout(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    return d.get("rollout") or {}

# What python is in use? Find evidence of the active python interpreter.
# In 16667 step13, python -m unittest ran with /opt/miniconda3/lib/python3.11
# But the verifier runs tests with /testbed/... and python 3.9/3.6.
# KEY: the agent's shell uses a DIFFERENT python than the testbed env!
# Let's check: does 'python' resolve to the conda testbed env or the base?

# Find commands probing python version
for task in ["django__django-16667", "django__django-11555", "astropy__astropy-13453", "pytest-dev__pytest-10356"]:
    ro = get_rollout(task)
    steps = ((ro.get("trace") or {}).get("steps")) or []
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        obs = s.get("observation")
        out = ""
        if obs:
            try:
                j = json.loads(obs.get("results")[0].get("content"))
                out = (j.get("output") or "") + (j.get("output_head") or "")
            except Exception:
                pass
        if "Python 3" in out or "python3." in out or "sys.version" in out:
            print(f"### {task} [{i}]:")
            print(out[:400])
            print("~~~")
