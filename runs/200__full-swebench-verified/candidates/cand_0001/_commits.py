import json, os

TRAJ = "trajectories"
FAILING = [
    "django__django-10554","django__django-11555","django__django-12325","django__django-13121",
    "django__django-13401","django__django-14007","django__django-14376","django__django-15629",
    "django__django-15930","django__django-16032","django__django-16667","matplotlib__matplotlib-22871",
    "pydata__xarray-6992","pylint-dev__pylint-4661","pylint-dev__pylint-4970","pytest-dev__pytest-10356",
    "pytest-dev__pytest-5787","sphinx-doc__sphinx-9258","sympy__sympy-15599","sympy__sympy-17139",
    "sympy__sympy-17630","sympy__sympy-18211","sympy__sympy-21612",
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
    d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    # find the LAST commit command and the last diff-producing command; also count "git commit" uses
    last_commit_idx = None
    n_commits = 0
    empty_diff = None  # did final `git diff` (vs HEAD) return empty?
    diff_vs_head = []
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            if "git add" in cmd and "git commit" in cmd:
                n_commits += 1
                last_commit_idx = idx
            # a `git diff` (working tree vs HEAD, i.e. no HEAD~) — used to produce final patch?
            if "git diff" in cmd or "git --no-pager diff" in cmd:
                diff_vs_head.append((idx, cmd[:80], obs[:120].replace("\n", " ⏎ ")))
    print(f"### {t}: n_commits={n_commits}")
    if diff_vs_head:
        for idx, cmd, obs in diff_vs_head[-3:]:
            print(f"   [{idx}] {cmd} -> {obs[:100]}")
    print()
