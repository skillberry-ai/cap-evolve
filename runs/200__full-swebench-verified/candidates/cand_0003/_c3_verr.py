import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

def obs_of(s):
    if not s.get("observation"):
        return "", None
    try:
        j = json.loads(s["observation"]["results"][0]["content"])
        return j.get("output", "") or "", j.get("returncode")
    except Exception:
        return "", None

# Now systematically: for each failing task, extract from the VERIFIER output the
# failing test names + error, and compare with what the agent's final commit changed.
FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667","pydata__xarray-6992","pylint-dev__pylint-4661",
    "pylint-dev__pylint-4970","pytest-dev__pytest-10356","pytest-dev__pytest-5787",
    "sympy__sympy-15599","sympy__sympy-17630","sympy__sympy-21612",
]
for task in FAILING:
    d = load(task)
    meta = ((d.get("rollout") or {}).get("metadata")) or {}
    vs = meta.get("verifier_stdout", "") or ""
    # failing tests
    fails = re.findall(r"^(?:FAILED|FAIL:|ERROR:?)\s+(\S+)", vs, re.M)
    print("=" * 100)
    print(task)
    print("  failing tests:", fails[:6])
    # the essential error (last traceback 'E   ' lines)
    es = re.findall(r"^E\s+(.*)$", vs, re.M)
    print("  E-lines:", es[:4])
    # collection errors?
    if "error during collection" in vs or "Interrupted: 1 error" in vs:
        print("  *** COLLECTION ERROR ***")
    if "ModuleNotFoundError" in vs:
        mods = set(re.findall(r"ModuleNotFoundError: No module named '(\w+)'", vs))
        print("  *** MISSING MODULES (verifier):", mods)
