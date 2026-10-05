import json, os, sys

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
INFRA = ["django__django-13809","django__django-15280","django__django-15741","django__django-16485",
         "sphinx-doc__sphinx-8638","sphinx-doc__sphinx-9367"]

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

def summarize(task):
    d = load(task)
    if d is None:
        return None
    r = d["rollout"]
    steps = (r.get("trace") or {}).get("steps") or []
    out_steps = (r.get("output") or {}).get("steps") or []
    meta = r.get("metadata") or {}
    vs = meta.get("verifier_stdout", "") or ""
    info = {
        "task": task,
        "reward": (d.get("score") or {}).get("reward"),
        "n_cmds": 0,
        "last_edit_idx": -1,
        "last_test_idx": -1,
        "tests_run_after_edit": False,
        "git_commit_used": False,
        "git_diff_tail": 0,
        "empty_diff_risk": False,
        "verifier_has_model_patch": "model patch" in vs.lower() or "git apply" in vs.lower(),
        "verifier_apply_ok": None,
        "n_fail_tests": vs.count("FAILED "),
        "n_pass_tests": vs.count("PASSED "),
    }
    # find apply result in verifier stdout
    low = vs.lower()
    for marker in ("applied model patch", "model patch applied", "successfully applied"):
        if marker in low:
            info["verifier_apply_ok"] = True
    if "error: patch" in low or "does not apply" in low:
        info["verifier_apply_ok"] = False
    cmds = []
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            info["n_cmds"] += 1
            cmds.append((i, cmd, rc, obs))
            lowc = cmd.lower()
            is_edit = (
                cmd.startswith("python -") or "sed -i" in cmd or "git apply" in cmd
                or ("path(" in lowc and ".write" in lowc) or "patch -p" in lowc
                or "git checkout --" in cmd or "git restore" in cmd
            )
            is_test = any(m in lowc for m in ("pytest", "py.test", "runtests.py", "unittest", "tox", "trial"))
            if is_edit:
                info["last_edit_idx"] = i
            if is_test and "conftest" not in lowc.split()[0:1]:
                info["last_test_idx"] = i
            if cmd.startswith("git commit") or "git commit -" in cmd:
                info["git_commit_used"] = True
    # trailing git diff / show commands (the "produce patch" step)
    tail_cmds = [c for (i, c, rc, o) in cmds[-6:]]
    info["git_diff_tail"] = sum(1 for c in tail_cmds if "git diff" in c or "git show" in c or "git --no-pager" in c)
    info["tests_run_after_edit"] = info["last_test_idx"] > info["last_edit_idx"]
    # how did the run END (mini-swe-agent completes with echo COMPLETE_TASK...)
    info["ends_with_submit"] = any("COMPLETE_TASK" in c for (i, c, rc, o) in cmds)
    # did the agent ever run a test that FAILED (rc != 0) and then NOT fix?
    info["final_cmd"] = cmds[-1][1][:120] if cmds else ""
    return info, cmds

for t in FAILING:
    res = summarize(t)
    if res is None:
        print(f"{t}: NO TRACE")
        continue
    info, cmds = res
    print(f"{t} r={info['reward']} cmds={info['n_cmds']} last_edit={info['last_edit_idx']} last_test={info['last_test_idx']} test_after_edit={info['tests_run_after_edit']} commit={info['git_commit_used']} taildiff={info['git_diff_tail']} Vfail={info['n_fail_tests']} Vpass={info['n_pass_tests']} apply_ok={info['verifier_apply_ok']}")
