import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# For EVERY failing task, find the LAST git commit diff the agent made (the final state),
# and whether the agent RAN the relevant tests at all + their result.
FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667","pydata__xarray-6992","pylint-dev__pylint-4661",
    "pylint-dev__pylint-4970","pytest-dev__pytest-10356","pytest-dev__pytest-5787",
    "sympy__sympy-15599","sympy__sympy-17630","sympy__sympy-21612",
]

def obs_of(s):
    if not s.get("observation"):
        return "", None
    try:
        j = json.loads(s["observation"]["results"][0]["content"])
        return j.get("output", "") or "", j.get("returncode")
    except Exception:
        return "", None

for task in FAILING:
    d = load(task)
    out = ((d.get("rollout") or {}).get("output")) or {}
    steps = out.get("steps") or []
    # Find all test runs and their results
    test_runs = []
    edits = 0
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            if re.search(r"(pytest|py\.test|runtests\.py)", c) and not c.startswith(("grep", "cat ", "ls")):
                # summarize result
                tail = (obs or "")[-400:]
                one = (c.splitlines()[0])[:120]
                test_runs.append((i, rc, one, tail))
    print("=" * 110)
    print(task)
    for (i, rc, one, tail) in test_runs[-3:]:
        print(f"  step {i} rc={rc}: {one}")
        for l in tail.splitlines()[-6:]:
            print(f"     | {l[:150]}")
