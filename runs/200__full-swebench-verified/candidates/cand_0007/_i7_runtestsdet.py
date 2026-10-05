import json, os

TRAJ = "trajectories"
# In 10554: "./runtests.py tests.queries.test_qs_combinators -k ordering -q || true" rc=0.
# What was its output? If it printed the FAILED test, then the agent HAD a working runner
# and ignored its result. Look at that exact step.

d = json.load(open(os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")))
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
        if "runtests.py" in cmd:
            print(f"@{idx} rc={rc} CMD: {cmd}")
            print("OUTPUT:")
            print(obs[:3000])
            print("~~~~")
