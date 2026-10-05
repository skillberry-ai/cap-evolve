import json, os, re, glob

TRAJ = "trajectories"

FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]
PASSING = [
    "django__django-12039", "django__django-12276", "django__django-13121",
    "django__django-13401", "django__django-13410", "django__django-13569",
    "django__django-14580", "django__django-15103", "django__django-15380",
    "django__django-15851", "django__django-15863", "django__django-15930",
    "matplotlib__matplotlib-22871", "matplotlib__matplotlib-24637",
    "scikit-learn__scikit-learn-25232", "sphinx-doc__sphinx-7910",
    "sphinx-doc__sphinx-8035", "sphinx-doc__sphinx-8475", "sphinx-doc__sphinx-8595",
    "sphinx-doc__sphinx-9258", "sympy__sympy-12096", "sympy__sympy-13480",
    "sympy__sympy-17139", "sympy__sympy-18211",
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

def analyze(task):
    p = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(p))
    steps = d["rollout"]["output"]["steps"]
    info = dict(n_cmds=0, pytest_tries=0, pytest_127=0, runtests_tries=0,
                runtests_ok=0, other_test_ok=0, test_fail_seen=0,
                edits_after_fail=0, final_commit=False, n_agent=0)
    first_fail_idx = None
    last_edit_idx = None
    cmds = []
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        info["n_agent"] += 1
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            info["n_cmds"] += 1
            cmds.append((idx, cmd, rc, (obs or "")[-150:]))
            low = cmd.lower()
            is_test = any(m in cmd for m in ("pytest", "runtests.py", "unittest", "tox", "trial", "py.test"))
            if is_test:
                if "pytest" in cmd and rc == 127:
                    info["pytest_tries"] += 1; info["pytest_127"] += 1
                elif "runtests.py" in cmd:
                    info["runtests_tries"] += 1
                    if isinstance(rc, int) and rc == 0:
                        info["runtests_ok"] += 1
                elif isinstance(rc, int) and rc != 0:
                    info["test_fail_seen"] += 1
                    if first_fail_idx is None:
                        first_fail_idx = idx
                elif isinstance(rc, int) and rc == 0:
                    info["other_test_ok"] += 1
            if cmd.startswith(("python -", "python3 -", "sed -i")) or "git apply" in cmd[:30] or "patch -p" in cmd[:30]:
                last_edit_idx = idx
            if cmd.startswith("git commit"):
                info["final_commit"] = True
    if first_fail_idx is not None and last_edit_idx is not None and last_edit_idx > first_fail_idx:
        info["edits_after_fail"] = 1
    return info, cmds

print(f"{'task':44s} {'cmds':>4s} {'py127':>5s} {'rt_ok':>5s} {'t_ok':>4s} {'t_fail':>6s} {'edit@>fail':>10s} {'commit':>6s}")
for t in FAILING:
    i, _ = analyze(t)
    print(f"{t:44s} {i['n_cmds']:4d} {i['pytest_127']:5d} {i['runtests_ok']:5d} {i['other_test_ok']:4d} {i['test_fail_seen']:6d} {i['edits_after_fail']:10d} {str(i['final_commit']):>6s}")
print()
for t in PASSING:
    i, _ = analyze(t)
    print(f"{t:44s} {i['n_cmds']:4d} {i['pytest_127']:5d} {i['runtests_ok']:5d} {i['other_test_ok']:4d} {i['test_fail_seen']:6d} {i['edits_after_fail']:10d} {str(i['final_commit']):>6s}")
