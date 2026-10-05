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

# check whether the agent made edits AFTER its last commit (uncommitted changes get lost?)
def steps_of(task):
    d = load(task)
    out = (d.get("rollout") or {}).get("output") or {}
    return out.get("steps") or []

for t in ["astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
          "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
          "django__django-16032","django__django-16667"]:
    steps = steps_of(t)
    last_commit = -1
    edit_after = []
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            if "git commit" in cmd:
                last_commit = i
    # check any python heredoc writes after last commit
    for i, s in enumerate(steps):
        if s.get("source") != "agent" or i <= last_commit:
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            if (cmd.startswith("python - <<") or cmd.startswith("python3 - <<") or "sed -i" in cmd[:20]) and "read_text" in cmd:
                edit_after.append(i)
    print(f"{t}: last_commit={last_commit}, writes_after_commit={edit_after}")
