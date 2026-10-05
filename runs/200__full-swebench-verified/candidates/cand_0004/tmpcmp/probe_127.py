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

TASKS = ["django__django-12325", "django__django-12708", "django__django-14007", "django__django-15629",
         "pytest-dev__pytest-5787", "sympy__sympy-15599", "pydata__xarray-6992", "pylint-dev__pylint-4661",
         "astropy__astropy-13453"]

for task in TASKS:
    d = load(task)
    steps = d["rollout"]["output"]["steps"]
    print("#" * 110)
    print("##", task)
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            if not c:
                continue
            obs, rc = obs_of(s)
            if rc == 127 or "No module named" in (obs or "") or "not found" in (obs or "").lower():
                print("--- CMD (rc=%s):" % rc)
                print(c[:400])
                print("    OBS:", (obs or "")[:500].replace("\n", "\n    "))
                print()
