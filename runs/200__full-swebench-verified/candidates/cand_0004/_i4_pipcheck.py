import json, os, re
TRAJ = "trajectories"
def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None
def obs_of(s):
    obs, rc = "", None
    if s.get("observation"):
        try:
            c = s["observation"]["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output", "") or ""
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc
def steps_of(task):
    d = load(task)
    out = (d.get("rollout") or {}).get("output") or {}
    return out.get("steps") or []

# What does pip install pytest do? In 15863 it installed pytest (step 14) then loadTestsFromName failed
# because asgiref was missing (django import fails). Then pip install asgiref (16) fixed it and unittest ran OK!
# Check the FULL output of step 16 in 15863.
steps = steps_of("django__django-15863")
s = steps[16]
for tc in (s.get("tool_calls") or []):
    cmd = (tc.get("arguments") or {}).get("command", "")
    obs, rc = obs_of(s)
    print("CMD:", cmd[:400])
    print("OBS:", (obs or "")[:1500])
