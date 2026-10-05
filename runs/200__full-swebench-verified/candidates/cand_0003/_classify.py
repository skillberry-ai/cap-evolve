import json, os, sys

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
        pytest_notfound=0,
        masked_verify=0,
        real_test_ok=0,
        real_test_fail=0,
        repro_attempted=0,
        repro_importfail=0,
        gitapply_badformat=0,
        end_diff_loop=0,
        edited_after_test=False,
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
            if "git apply" in cmd and isinstance(rc, int) and rc != 0:
                stats["gitapply_badformat"] += 1
            is_test = any(m in cmd for m in TESTCMD_MARKERS)
            if is_test:
                if "pytest" in cmd and rc == 127:
                    stats["pytest_notfound"] += 1
                elif ("|| true" in cmd or "|| exit 0" in cmd or "2>/dev/null" in low):
                    stats["masked_verify"] += 1
                elif rc == 0 and ("passed" in (obs or "").lower() or "ok" in (obs or "").lower()):
                    stats["real_test_ok"] += 1
                elif rc not in (0, None):
                    stats["real_test_fail"] += 1
                    if first_real_fail_idx is None:
                        first_real_fail_idx = idx
            if cmd.startswith("python -") or "python - <<" in cmd or "python << " in cmd:
                if "import " in cmd or "repro" in low:
                    stats["repro_attempted"] += 1
                    if isinstance(rc, int) and rc != 0:
                        stats["repro_importfail"] += 1
            if (cmd.startswith("python -") or "sed -i" in cmd or ("Path(" in cmd and ".write" in cmd)):
                last_edit_idx = idx
    if first_real_fail_idx is not None and last_edit_idx is not None and last_edit_idx > first_real_fail_idx:
        stats["edited_after_test"] = True
    # count trailing identical git diff commands (the end loop)
    tail = [ (tc.get("arguments") or {}).get("command","") for s in steps[-8:] if s.get("source")=="agent" for tc in (s.get("tool_calls") or []) ]
    n_diff_tail = sum(1 for c in tail if "git diff" in c or "git --no-pager diff" in c or "git --no-pager show HEAD" in c)
    stats["end_diff_loop"] = n_diff_tail
    return stats, first_real_fail_idx, last_edit_idx

print(f"{'task':44s} {'steps':>5s} {'pytnf':>5s} {'mask':>4s} {'t_ok':>4s} {'t_fail':>5s} {'repro':>5s} {'rifail':>6s} {'apply':>5s} {'taildiff':>8s} {'edit>test':>9s}")
for t in FAILING:
    try:
        st, ff, le = classify(t)
        print(f"{t:44s} {st['n_steps']:5d} {st['pytest_notfound']:5d} {st['masked_verify']:4d} {st['real_test_ok']:4d} {st['real_test_fail']:5d} {st['repro_attempted']:5d} {st['repro_importfail']:6d} {st['gitapply_badformat']:5d} {st['end_diff_loop']:8d} {str(st['edited_after_test']):>9s}")
    except FileNotFoundError:
        print(f"{t}: NO TRACE")
