import json, os

TRAJ = "trajectories"
# The step @20 in 16667 ran `pytest ...` rc=1 with EMPTY output. This means the command
# TIMED OUT (or was truncated). Note `pip install -e .` on Django is SLOW (builds the
# package). The agent then never saw test results. Look at how long steps took — check
# the mini-swe-agent trajectory json for timestamps/durations if present.

p = os.path.join(TRAJ, "django__django-16667__cand_0002__t0.json")
d = json.load(open(p))
# check raw keys at rollout level
print("rollout keys:", list(d["rollout"].keys()))
md = d["rollout"].get("metadata") or {}
print("metadata keys:", list(md.keys()))
out = d["rollout"]["output"]
print("output keys:", list(out.keys()))
# observation structure of step 20
s20 = out["steps"][20]
print("step20 keys:", list(s20.keys()))
print(json.dumps(s20.get("observation"), indent=1)[:2000])
