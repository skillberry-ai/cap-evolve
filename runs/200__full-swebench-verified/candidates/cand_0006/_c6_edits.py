import json, os, glob

TRAJ = "trajectories"

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

# For each failing task: dump the edit command + its observation, and the git diff HEAD at end,
# plus any python heredoc repro results
for t in FAILING:
    p = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    d = json.load(open(p))
    steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
    print("#" * 100)
    print("##", t)
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            # show edit attempts and their results
            if cmd.startswith("python - <<") or cmd.startswith("python3 - <<") or "git apply" in cmd[:60]:
                ok = isinstance(rc, int) and rc == 0
                err = ""
                if not ok:
                    err = (obs or "")[-400:].replace("\n", " | ")
                print(f"  @{idx} rc={rc} :: {cmd[:90].replace(chr(10), ' ')}")
                if not ok:
                    print(f"      ERR: {err[:250]}")
