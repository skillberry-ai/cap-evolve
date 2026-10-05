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
PASSING = [
    "astropy__astropy-13453","django__django-12039","django__django-12276","django__django-12708",
    "django__django-13410","django__django-13569","django__django-13809","django__django-14580",
    "django__django-15103","django__django-15380","django__django-15851","django__django-15863",
    "django__django-16485","matplotlib__matplotlib-24637","pydata__xarray-6461",
    "scikit-learn__scikit-learn-25232","sphinx-doc__sphinx-7910","sphinx-doc__sphinx-8035",
    "sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595","sphinx-doc__sphinx-9367","sympy__sympy-12096",
    "sympy__sympy-13480","sympy__sympy-24213",
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

TESTCMD_MARKERS = ("pytest", "py.test", "runtests.py", "unittest", "trial", "tox", "nosetests")

def classify(task):
    d = json.load(open(os.path.join(TRAJ, f"{task}__seed__t0.json")))
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    stats = dict(
        pytest_notfound=0,      # rc=127 pytest
        masked_verify=0,        # test cmd with || true / || exit 0 / 2>/dev/null
        real_test_ok=0,         # a test command rc==0 with pass evidence
        real_test_fail=0,       # a test command with visible FAIL/ERROR output (rc!=0 or FAILED text)
        repro_attempted=0,      # python - << scripts that import the package
        repro_importfail=0,     # repro failed with settings/import error
        gitapply_badformat=0,   # git apply rc=128 unrecognized input
        end_diff_loop=0,        # trailing repeated git diff commands
        edited_after_test=False,# made edits AFTER seeing a real test failure (iteration!)
        n_steps=0,
    )
    first_real_fail_idx = None
    last_edit_idx = None
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        stats["n_steps"] += 1
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            low = cmd.lower()
            is_test = any(m in cmd for m in TESTCMD_MARKERS) and not cmd.strip().startswith("grep") and " sed " not in low[:20]
            if is_test:
                if rc == 127:
                    stats["pytest_notfound"] += 1
                if "|| true" in cmd or "|| exit 0" in cmd or "2>/dev/null" in cmd:
                    stats["masked_verify"] += 1
                passed_ev = ("OK" in obs) or ("passed" in obs) or (" 0 failed" in obs)
                failed_ev = ("FAILED" in obs) or ("FAIL:" in obs) or ("ERROR:" in obs) or ("failures=" in obs) or ("errors=" in obs)
                if isinstance(rc, int) and rc == 0 and passed_ev:
                    stats["real_test_ok"] += 1
                if failed_ev or (isinstance(rc, int) and rc not in (0,)):
                    if "not found" not in obs and "No module named" not in obs:
                        stats["real_test_fail"] += 1
                        if first_real_fail_idx is None:
                            first_real_fail_idx = idx
            if cmd.startswith("git apply") and isinstance(rc, int) and rc != 0:
                stats["gitapply_badformat"] += 1
            if cmd.startswith("python") and "<<" in cmd and ("import" in cmd or "from " in cmd):
                stats["repro_attempted"] += 1
                if "ImproperlyConfigured" in obs or "Modulenotfound" in obs.replace("ModuleNotFoundError","Modulenotfound") or "ImportError" in obs or "Settings" in obs:
                    stats["repro_importfail"] += 1
            if (cmd.startswith("python") and "<<" in cmd) or cmd.startswith("sed -i") or "write_text" in cmd:
                last_edit_idx = idx
    if first_real_fail_idx is not None and last_edit_idx is not None and last_edit_idx > first_real_fail_idx:
        stats["edited_after_test"] = True
    # trailing repeated diff loop
    tail_cmds = []
    for s in steps[-8:]:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            tail_cmds.append((tc.get("arguments") or {}).get("command", ""))
    n_diff_tail = 0
    for c in reversed(tail_cmds):
        if "git" in c and "diff" in c:
            n_diff_tail += 1
        else:
            break
    stats["end_diff_loop"] = n_diff_tail
    return stats

rows = []
print(f"{'task':<36} {'T':<4} {'steps':>5} {'py127':>5} {'mask':>4} {'tOK':>3} {'tFAIL':>5} {'repro':>5} {'repImp':>6} {'applyF':>6} {'iter':>5} {'tail':>4}")
for t in FAILING + PASSING:
    s = classify(t)
    tag = "FAIL" if t in FAILING else "PASS"
    print(f"{t:<36} {tag:<4} {s['n_steps']:>5} {s['pytest_notfound']:>5} {s['masked_verify']:>4} {s['real_test_ok']:>3} "
          f"{s['real_test_fail']:>5} {s['repro_attempted']:>5} {s['repro_importfail']:>6} {s['gitapply_badformat']:>6} "
          f"{str(s['edited_after_test'])[:1]:>5} {s['end_diff_loop']:>4}")
