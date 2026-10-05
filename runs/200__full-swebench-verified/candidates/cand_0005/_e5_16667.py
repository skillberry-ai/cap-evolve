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

d = load("django__django-16667")
steps = (d["rollout"].get("trace") or {}).get("steps") or []
for i, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    obs, rc = obs_of(s)
    if i in (18, 19, 20, 21):
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            print(f"--- [{i}] rc={rc}: {c[:300]}")
            print("OUT:", (obs or "")[-2500:])
            print()
