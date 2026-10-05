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

# For django__django-11555 the FAIL is in verifier. Look at the beginning of verifier stdout:
d = load("django__django-11555")
vs = (d["rollout"].get("metadata") or {}).get("verifier_stdout", "")
print("=== django-11555 verifier head ===")
print(vs[:2200])
