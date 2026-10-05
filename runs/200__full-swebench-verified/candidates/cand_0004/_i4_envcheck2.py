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

# The environment: /testbed is the repo. python3 is 3.11 (from traceback paths above).
# Interesting: for 11555, 'python3' imported django from /testbed OK at step 27, but at step 28 the
# OrderBy import hit asgiref missing. So 'python3' vs 'python' may differ, and django import partially works.
# Key question: does 'python' point to a different interpreter than 'python3'?
# Check which python commands succeeded across tasks:
FAILING = ["django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667","astropy__astropy-13453"]
import collections
for t in FAILING:
    steps = steps_of(t)
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            if re.match(r"^(python3?|pytest) ", cmd.strip()) or cmd.startswith("python - <<") or cmd.startswith("python3 - <<"):
                interp = "python3" if cmd.startswith("python3") else ("python" if cmd.startswith("python") else "pytest")
                print(f"[{t:30s} {i:3d}] {interp:8s} rc={rc}  {cmd.splitlines()[0][:80]}")
