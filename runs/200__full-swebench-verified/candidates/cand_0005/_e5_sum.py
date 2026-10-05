import json, os, sys, re

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
        return
    r = d["rollout"]
    steps = (r.get("trace") or {}).get("steps") or (r.get("output") or {}).get("steps") or []
    meta = r.get("metadata") or {}
    vs = meta.get("verifier_stdout", "") or ""
    info = dict(task=task, reward=(d.get("score") or {}).get("reward"),
                n_steps=0, n_cmds=0, last_cmd="", submit_seen=False,
                git_commit=0, empty_final_diff=None)
    cmds = []
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        info["n_steps"] += 1
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            if not c:
                continue
            cmds.append(c)
            info["n_cmds"] += 1
            if "COMPLETE_TASK_AND_SUBMIT" in c:
                info["submit_seen"] = True
            if c.startswith("git commit"):
                info["git_commit"] += 1
    info["last_cmd"] = cmds[-1][:120] if cmds else ""
    info["tail5"] = [c[:100] for c in cmds[-5:]]
    # verifier: find FAIL_TO_PASS / PASS_TO_PASS result lines
    nfail = len(re.findall(r"FAILED", vs))
    npass = len(re.findall(r"PASSED", vs))
    info["verifier_FAILED"] = nfail
    info["verifier_PASSED"] = npass
    # did the model patch apply?
    info["apply_error"] = ("error" in vs.lower() and "apply" in vs.lower())
    print(f"{task:42s} r={info['reward']} steps={info['n_steps']:3d} cmds={info['n_cmds']:3d} "
          f"submit={info['submit_seen']:d} commits={info['git_commit']} vFAIL={nfail} vPASS={npass}")
    print(f"    tail: {info['tail5']}")

print("== FAILING ==")
for t in FAILING:
    summarize(t)
print()
print("== PASSING (sample) ==")
for t in PASSING[:8]:
    summarize(t)
