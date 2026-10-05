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

# For each failing task, check: how many git commits did the agent make, and what was the last state?
# Also find whether the harness resets with 'git checkout' before test patch (test files might conflict with the agent's modifications to tests)
FAILING = ["astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667"]
for t in FAILING:
    steps = steps_of(t)
    commits, edits, testfiles = [], [], []
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            if "git commit" in cmd:
                commits.append(i)
            if cmd.startswith("python - <<") or cmd.startswith("python3 - <<"):
                edits.append((i, cmd[:120]))
    print(f"### {t}: commits at {commits}, python-heredoc edits at {[i for i,_ in edits]}")
