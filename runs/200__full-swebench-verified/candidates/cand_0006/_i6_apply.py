import json, os

TRAJ = './trajectories'

FAILING = set([
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
])

def get_steps(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    ro = d.get("rollout") or {}
    return ((ro.get("trace") or {}).get("steps")) or []

def parse_obs(s):
    obs = s.get("observation")
    if not obs:
        return None
    try:
        c = obs.get("results")[0].get("content")
        return json.loads(c)
    except Exception:
        return None

# For each of the 10 always-failing tasks, extract:
# 1. All git apply attempts and their errors
# 2. What files were ACTUALLY changed (from the final git diff / commit)
# 3. Whether .bak files or other junk files got committed
for task in sorted(FAILING):
    steps = get_steps(task)
    print("=" * 100)
    print(f"### {task}")
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command") or ""
            j = parse_obs(s)
            rc = (j or {}).get("returncode")
            out = (j or {}).get("output") or ""
            if "git apply" in cmd:
                print(f"  [{i}] GIT APPLY rc={rc}")
                print(f"      cmd: {cmd[:400]!r}")
                if rc not in (0, None):
                    print(f"      err: {out[:300]!r}")
            if "git add -A" in cmd or ("git commit" in cmd):
                print(f"  [{i}] GIT COMMIT: {cmd[:160]!r} -> out tail: {out.strip().splitlines()[-1] if out.strip() else ''!r}")
            if ".bak" in cmd and "rm" in cmd:
                print(f"  [{i}] BAK CLEANUP: {cmd[:160]!r}")
