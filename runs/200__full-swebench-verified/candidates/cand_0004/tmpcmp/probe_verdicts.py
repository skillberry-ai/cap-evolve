import json, os, re

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
TRAJ = os.path.join(BASE, "trajectories")

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

# Which final-observation error does each failing task's verifier show? And did the agent's patch
# get applied by the harness? Look at "git apply" in verifier output and errors.
for task in ["astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
             "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
             "django__django-16032","django__django-16667","pydata__xarray-6992","pylint-dev__pylint-4661",
             "pylint-dev__pylint-4970","pytest-dev__pytest-10356","pytest-dev__pytest-5787",
             "sympy__sympy-15599","sympy__sympy-17630","sympy__sympy-21612"]:
    d = load(task)
    meta = d["rollout"].get("metadata") or {}
    vs = meta.get("verifier_stdout", "") or ""
    # Look for apply errors and the final verdict
    lines = vs.splitlines()
    interesting = [l for l in lines if re.search(r"(error|Error|FAILED|PASSED|not found|No module|SWEBench results)", l)]
    print("=" * 100)
    print("##", task)
    for l in interesting[-14:]:
        print("  ", l[:200])
