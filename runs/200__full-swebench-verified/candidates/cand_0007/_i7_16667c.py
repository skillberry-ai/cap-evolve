import json, os

TRAJ = "trajectories"
# In django__django-16667 the agent ran `pip install -e .` and then `pytest` collected
# the test file but the run FAILED (rc=1) with empty output. Why? Look at that exact
# step's full observation and surrounding steps.

p = os.path.join(TRAJ, "django__django-16667__cand_0002__t0.json")
d = json.load(open(p))
steps = d["rollout"]["output"]["steps"]

for idx, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    obs = ""
    rc = None
    if s.get("observation"):
        try:
            c = s["observation"]["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output", "") or ""
            rc = j.get("returncode")
        except Exception:
            pass
    for tc in (s.get("tool_calls") or []):
        cmd = (tc.get("arguments") or {}).get("command", "")
        if idx >= 17:
            print(f"=== @{idx} rc={rc}")
            print("CMD:", cmd[:400])
            print("OUT:", obs[:2000])
            print()
