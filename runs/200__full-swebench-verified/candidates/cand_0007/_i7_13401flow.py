import json, os

TRAJ = "trajectories"
# django-13401 PASSED. It ran `pytest -q django/db/models -q -k field || true` rc=0.
# Was that "not found" or a real run? Look at output.
d = json.load(open(os.path.join(TRAJ, "django__django-13401__cand_0002__t0.json")))
steps = d["rollout"]["output"]["steps"]

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

for idx, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    obs, rc = obs_of(s)
    for tc in (s.get("tool_calls") or []):
        cmd = (tc.get("arguments") or {}).get("command", "")
        if "pytest" in cmd:
            print(f"@{idx} rc={rc} CMD: {cmd}")
            print("OUT:", obs[:2000])
