import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# print verifier stdout for several failing tasks, focusing on the SWEBench results and test summary
for task in ["django__django-11555","django__django-12325","django__django-12708","django__django-14007",
             "django__django-14376","django__django-15629","django__django-16032","django__django-16667",
             "pylint-dev__pylint-4661","pylint-dev__pylint-4970","pytest-dev__pytest-10356",
             "pydata__xarray-6992","astropy__astropy-13453"]:
    d = load(task)
    vs = (d["rollout"].get("metadata") or {}).get("verifier_stdout", "") or ""
    low = vs.lower()
    # find FAILED test names: SWE-bench harness prints test result lines
    m = re.findall(r"(FAILED|ERROR)\s+([\w\.\[\]/<>]+)", vs)
    print(f"== {task} len={len(vs)}")
    # print the last 1200 chars which usually contain the summary
    print(vs[-1200:])
    print("-----")
