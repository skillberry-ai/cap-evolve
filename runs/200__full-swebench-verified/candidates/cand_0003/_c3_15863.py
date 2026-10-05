import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

def obs_of(s):
    if not s.get("observation"):
        return "", None
    try:
        j = json.loads(s["observation"]["results"][0]["content"])
        return j.get("output", "") or "", j.get("returncode")
    except Exception:
        return "", None

# django-15863: how did it get tests running after pip install asgiref?
task = "django__django-15863"
d = load(task)
out = ((d.get("rollout") or {}).get("output")) or {}
steps = out.get("steps") or []
for i, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    for tc in (s.get("tool_calls") or []):
        c = (tc.get("arguments") or {}).get("command", "")
        obs, rc = obs_of(s)
        if i >= 10 and i <= 22:
            print(f"--- step {i} rc={rc}: {c[:250]}")
            tail = (obs or "")[-600:]
            for l in tail.splitlines()[-10:]:
                print(f"   | {l[:150]}")
            print()
