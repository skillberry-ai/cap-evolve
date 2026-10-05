import json, os, re

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
TRAJ = os.path.join(BASE, "trajectories")

FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667",
    # also these were failing for cand_0002 (same rollouts in trajectories/)
    "pydata__xarray-6992","pylint-dev__pylint-4661","pylint-dev__pylint-4970",
    "pytest-dev__pytest-10356","pytest-dev__pytest-5787",
    "sympy__sympy-15599","sympy__sympy-17630","sympy__sympy-21612",
]
PASSING = [
    "django__django-12039","django__django-12276","django__django-13121","django__django-13401",
    "django__django-13410","django__django-13569","django__django-14580","django__django-15103",
    "django__django-15380","django__django-15851","django__django-15863","django__django-15930",
    "matplotlib__matplotlib-22871","matplotlib__matplotlib-24637","pydata__xarray-6461",
    "scikit-learn__scikit-learn-25232","sphinx-doc__sphinx-7910","sphinx-doc__sphinx-8035",
    "sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595","sphinx-doc__sphinx-9258","sympy__sympy-12096",
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
    o = s.get("observation")
    if o:
        try:
            c = o["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output") or j.get("output_head") or ""
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc

TEST_MARKERS = re.compile(r"(pytest|py\.test|runtests\.py|python -m unittest|python3 -m unittest|tox )")

def summarize(task):
    d = load(task)
    if d is None:
        return f"{task:44s} NOT FOUND"
    reward = (d.get("score") or {}).get("reward")
    steps = d["rollout"]["output"]["steps"]
    n_cmds = 0
    commits = 0
    n_rc127 = 0
    modnotfound = {}   # module -> count  (from agent's own runs)
    test_runs = 0
    test_fail_runs = 0
    test_pass_runs = 0
    empty_diff_end = None
    last_cmd = ""
    tail_cmds = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            if not c:
                continue
            n_cmds += 1
            obs, rc = obs_of(s)
            if "git commit" in c[:20] or c.startswith("git commit"):
                commits += 1
            if TEST_MARKERS.search(c) and not c.startswith(("grep", "cat", "sed", "ls", "nl ")):
                test_runs += 1
                if rc not in (0, None):
                    test_fail_runs += 1
                elif rc == 0:
                    test_pass_runs += 1
            if rc == 127:
                n_rc127 += 1
            m = re.search(r"ModuleNotFoundError: No module named '([^']+)'", obs or "")
            if m and rc not in (0,):
                modnotfound[m.group(1)] = modnotfound.get(m.group(1), 0) + 1
            tail_cmds.append(c)
    tail = tail_cmds[-3:]
    return (f"{task:44s} r={reward} cmds={n_cmds:3d} commits={commits} testruns={test_runs} "
            f"tfail={test_fail_runs} tpass={test_pass_runs} rc127={n_rc127} "
            f"modnotfound={modnotfound}")

print("== FAILING ==")
for t in FAILING:
    print(summarize(t))
print()
print("== PASSING (sample) ==")
for t in PASSING[:12]:
    print(summarize(t))
