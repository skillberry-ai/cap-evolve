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

task = "django__django-10554"
d = load(task)
r = d["rollout"]
steps = (r.get("trace") or {}).get("steps") or []
meta = r.get("metadata") or {}
vs = meta.get("verifier_stdout", "") or ""
print("=== verifier stdout (first 6000) ===")
print(vs[:6000])
