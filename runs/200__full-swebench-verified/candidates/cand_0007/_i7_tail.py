import json, os

TRAJ = "trajectories"
# For each failing task, check: did the agent's final committed diff include the
# model patch? Did the agent leave stray files? Did the agent COMMIT?
FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]

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

for t in FAILING:
    p = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    d = json.load(open(p))
    steps = d["rollout"]["output"]["steps"]
    n_steps = len(steps)
    n_cmd = 0
    last_cmds = []
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            n_cmd += 1
            last_cmds.append((idx, cmd))
    print("##", t, "steps:", n_steps, "cmds:", n_cmd)
    for idx, c in last_cmds[-3:]:
        print("   @", idx, "::", c[:120].replace("\n", " "))
