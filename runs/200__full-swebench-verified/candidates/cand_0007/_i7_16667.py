import json, os

TRAJ = "trajectories"

def obs_of(s):
    obs, rc = "", None
    if s.get("observation"):
        try:
            c = s["observation"]["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output", "")
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc

task = "django__django-16667"
p = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
d = json.load(open(p))
steps = d["rollout"]["output"]["steps"]
for idx, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    for tc in (s.get("tool_calls") or []):
        cmd = (tc.get("arguments") or {}).get("command", "")
        obs, rc = obs_of(s)
        if "pytest" in cmd or "unittest" in cmd or "pip install" in cmd:
            print(f"[{idx}] rc={rc} CMD: {cmd[:150]}")
            print("  FULL OUTPUT:")
            print((obs or "")[:1500])
            print("~~~~")
