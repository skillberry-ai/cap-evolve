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

# Understand how the harness computes the model patch: does the agent's commit survive?
# The verifier stdout starts mid-way. Let me check the REWARD metadata and any 'git' commands the harness logs.
task = "django__django-16667"
d = load(task)
meta = ((d.get("rollout") or {}).get("metadata") or {})
print("metadata keys:", list(meta.keys()))
rj = meta.get("reward_json")
print("reward_json:", json.dumps(rj)[:500] if rj else rj)
# Look at the notes field of the output
out = (d.get("rollout") or {}).get("output") or {}
notes = out.get("notes")
print("notes:", json.dumps(notes)[:600] if notes else notes)
