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

# 1. Did ANY task discover the right python environment? e.g. /opt/miniconda3/envs/testbed/bin/python?
# The verifier runs from an env where django IS importable. Look for env activation attempts.
ALL_FAIL = ["django__django-10554","django__django-11555","django__django-12325","django__django-12708",
            "django__django-14007","django__django-14376","django__django-15629","django__django-16032","django__django-16667"]
found = []
for t in ALL_FAIL:
    steps = steps_of(t)
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            if "miniconda" in cmd or "conda" in cmd or "envs" in cmd or "PATH=" in cmd or "pip install" in cmd:
                obs, rc = obs_of(s)
                found.append((t, i, rc, cmd[:150], (obs or "")[:200].replace("\n"," | ")))
for f in found:
    print(f)
if not found:
    print("No env/pip attempts in failing django tasks")
