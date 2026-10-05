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

# In django tasks the repro scripts also probably failed with ModuleNotFoundError: django? Check all python heredoc runs in failing tasks and their rc
FAILING = ["django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667"]
for t in FAILING:
    steps = steps_of(t)
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            if cmd.startswith("python - <<") or cmd.startswith("python3 - <<"):
                # is it an edit (writes file) or a repro (imports)?
                is_edit = "write_text" in cmd
                first_err = ""
                for l in (obs or "").splitlines():
                    if "Error" in l or "error" in l:
                        first_err = l.strip()[:130]
                        break
                print(f"[{t} {i}] rc={rc} edit={is_edit} err={first_err!r}")
