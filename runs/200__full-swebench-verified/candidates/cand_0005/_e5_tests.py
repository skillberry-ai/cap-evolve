import json, os, re

TRAJ = "trajectories"

FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667","pylint-dev__pylint-4661","pylint-dev__pylint-4970",
    "pytest-dev__pytest-10356","pytest-dev__pytest-5787","sphinx-doc__sphinx-9258","sympy__sympy-15599",
    "sympy__sympy-17630","sympy__sympy-21612","matplotlib__matplotlib-22871","pydata__xarray-6992",
]
PASSING = [
    "django__django-12039","django__django-12276","django__django-13121","django__django-13401",
    "django__django-13410","django__django-13569","django__django-14580","django__django-15103",
    "django__django-15380","django__django-15851","django__django-15863","django__django-15930",
    "matplotlib__matplotlib-24637","scikit-learn__scikit-learn-25232","sphinx-doc__sphinx-7910",
    "sphinx-doc__sphinx-8035","sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595","sympy__sympy-12096",
    "sympy__sympy-13480","sympy__sympy-17139","sympy__sympy-18211",
]

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

TEST_RE = re.compile(r"(\bpytest\b|py\.test|runtests\.py|python3? -m unittest|python3? -m pytest|-m pytest\b)")

def summarize(task):
    d = load(task)
    if d is None:
        return
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    rows = []
    n_cmds = 0
    test_runs = []   # (idx, rc, cmd_snippet)
    n_notfound = 0
    n_module_err = 0
    n_gitapply_fail = 0
    last_test_ok_idx = -1
    last_edit_idx = -1
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            if not c:
                continue
            n_cmds += 1
            if c.startswith(("git apply", "applypatch")) and rc not in (0, None):
                n_gitapply_fail += 1
            if TEST_RE.search(c) and not c.startswith(("grep","cat","sed","nl","ls")):
                test_runs.append((i, rc, c[:150]))
                o = (obs or "").lower()
                if rc == 127 or "not found" in o and "pytest" in o:
                    n_notfound += 1
                if "modulenotfounderror" in o or "no module named" in o:
                    n_module_err += 1
                if rc == 0:
                    last_test_ok_idx = i
            if re.search(r"(sed -i|<< 'PY'|<< \"PY\"|\.write_text|cat > )", c) and "git diff" not in c:
                last_edit_idx = i
    print(f"== {task} r={d['score']['reward']} cmds={n_cmds} testruns={len(test_runs)} "
          f"rc127/notfound={n_notfound} modulenotfound={n_module_err} gitapplyfail={n_gitapply_fail} "
          f"last_edit={last_edit_idx} last_testok={last_test_ok_idx}")
    for (i, rc, snip) in test_runs[:14]:
        print(f"    [{i}] rc={rc}: {snip}")

for t in FAILING:
    summarize(t)
