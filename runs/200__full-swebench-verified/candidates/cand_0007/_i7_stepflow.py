import json, os

TRAJ = "trajectories"
# Look at 11555's runtests run and 14376's pytest run in detail — rc=0 but were they real?
for t, needle in [("django__django-11555", "runtests.py"),
                  ("django__django-14376", "pytest -q django/db/backends/mysql")]:
    d = json.load(open(os.path.join(TRAJ, f"{t}__cand_0002__t0.json")))
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

    print("#" * 90)
    print("##", t)
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            if needle in cmd:
                print(f"@{idx} rc={rc} CMD: {cmd[:200]}")
                print("OUTPUT:")
                print(obs[:2500])
                print("~~~~")
