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

def analyze(task):
    data = json.load(open(os.path.join(TRAJ, f"{task}__seed__t0.json")))
    steps = (data["rollout"].get("trace") or {}).get("steps") or []
    result = {
        "task": task,
        "reward": data["score"]["reward"],
        "n_steps": len(steps),
        "git_apply_fail": 0,
        "pytest_127": 0,
        "runtests_used": False,
        "unittest_used": False,
        "test_verified_pass": False,  # any test command with rc==0 showing pass
        "import_fail": 0,
        "file_edit_via_python": 0,
        "env_probes": 0,
    }
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = "", None
            if s.get("observation"):
                try:
                    c = s["observation"]["results"][0]["content"]
                    j = json.loads(c)
                    obs = j.get("output", "")
                    rc = j.get("returncode")
                except Exception:
                    pass
            if cmd.startswith("git apply") and isinstance(rc, int) and rc != 0:
                result["git_apply_fail"] += 1
            if cmd.strip().startswith("pytest") and rc == 127:
                result["pytest_127"] += 1
            if "runtests.py" in cmd and not cmd.startswith("grep"):
                result["runtests_used"] = True
            if "python -m unittest" in cmd:
                result["unittest_used"] = True
            if isinstance(rc, int) and rc == 0 and (" passed" in obs or "OK" in obs):
                result["test_verified_pass"] = True
            if ("ModuleNotFoundError" in obs) or ("ImportError" in obs):
                result["import_fail"] += 1
            if ("p.read_text()" in cmd) and ".replace(" in cmd:
                result["file_edit_via_python"] += 1
            if cmd.startswith(("python -V", "python3 -V", "python -c", "python3 -c", "pip", "pip3", "which")):
                result["env_probes"] += 1
    return result

rows = []
for t in FAILING + PASSING:
    rows.append(analyze(t))

print(f"{'task':<38} {'r':>3} {'steps':>5} {'applyF':>6} {'py127':>5} {'runT':>5} {'unit':>4} {'impF':>4} {'pyEdit':>6} {'envP':>4}")
for r in rows:
    tag = "FAIL" if r["reward"] == 0 else "PASS"
    print(f"{r['task']:<38} {tag:>3} {r['n_steps']:>5} {r['git_apply_fail']:>6} {r['pytest_127']:>5} "
          f"{str(r['runtests_used']):>5} {str(r['unittest_used'])[:1]:>4} {r['import_fail']:>4} {r['file_edit_via_python']:>6} {r['env_probes']:>4}")
