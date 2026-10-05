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

TEST_RE = re.compile(r"^(pytest|py\.test|python3? -m pytest|python3? -m unittest|\.\/runtests\.py|python3? tests/runtests\.py|tests/runtests\.py|make test|tox)")

def envinfo(task):
    d = load(task)
    out = (d.get("rollout") or {}).get("output") or {}
    steps = out.get("steps") or []
    reward = (d.get("score") or {}).get("reward")
    print(f"### {task}  reward={reward}")
    n_test = 0
    n_test_ok = 0
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            if TEST_RE.search(cmd.strip()):
                n_test += 1
                ok = rc == 0
                if ok: n_test_ok += 1
                print(f"  [{i}] rc={rc} {'OK ' if ok else 'BAD'} {cmd[:160]}")
                if rc not in (0,):
                    tail = [l for l in (obs or "").splitlines() if l.strip()][-3:]
                    for l in tail:
                        print("      >", l[:160])
    if n_test == 0:
        print("  (no test commands run)")

for t in ["astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
          "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
          "django__django-16032","django__django-16667"]:
    envinfo(t)
