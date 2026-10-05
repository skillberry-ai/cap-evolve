import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# Deep-dive 2 clusters:
# CLUSTER A: tasks where pytest is NOT AVAILABLE (rc=127 or 'No module named pytest')
#   -> the agent cannot verify; it makes ONE guess-edit and finishes.
#   The verifier runs the tests with the repo's runner (django: tests/runtests.py, sympy: pytest, ...)
#   Q: can the agent install pytest? django-15863 (PASSING) did `pip install pytest` and it
#   worked (though it then used unittest because asgiref missing). sympy-13480 did pip install pytest --user.
#
# CLUSTER B: the agent's fix is WRONG but it never found out because tests never ran.
#
# Let me quantify: for each failing task, (1) did any test command RUN successfully (rc=0 with
# test output)? (2) What was the final commit diff size?

def obs_of(s):
    if not s.get("observation"):
        return "", None
    try:
        j = json.loads(s["observation"]["results"][0]["content"])
        return j.get("output", "") or "", j.get("returncode")
    except Exception:
        return "", None

FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667","pydata__xarray-6992","pylint-dev__pylint-4661",
    "pylint-dev__pylint-4970","pytest-dev__pytest-10356","pytest-dev__pytest-5787",
    "sympy__sympy-15599","sympy__sympy-17630","sympy__sympy-21612",
]

for task in FAILING:
    d = load(task)
    out = ((d.get("rollout") or {}).get("output")) or {}
    steps = out.get("steps") or []
    ran_ok = False
    ran_fail = False
    attempted = 0
    notfound = 0
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            if re.search(r"(pytest|py\.test|runtests\.py| -m unittest|unittest\.TextTestRunner)", c) and not c.startswith(("grep", "cat ", "ls")):
                attempted += 1
                o = obs or ""
                if rc == 127 or "No module named pytest" in o or "not found" in o.split("\n")[0]:
                    notfound += 1
                elif re.search(r"(\d+ (passed|failed)|Ran \d+ tests|FAIL|ERROR|ok)", o):
                    if rc == 0 and ("passed" in o or "ok" in o):
                        ran_ok = True
                    else:
                        ran_fail = True
    meta = ((d.get("rollout") or {}).get("metadata")) or {}
    vs = meta.get("verifier_stdout", "") or ""
    m = re.search(r"SWEBench results starts here\s*(\w+)", vs)
    verdict = m.group(1) if m else "?"
    print(f"{task:42s} attempted={attempted:2d} notfound={notfound:2d} ranOK={ran_ok:d} ranFAIL={ran_fail:d} verdict={verdict}")
