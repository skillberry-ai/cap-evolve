import json, os, re

TRAJ = "trajectories"

FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667",
]

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

# For each failing task: show the LAST agent edit (the fix attempt), the test runs after it,
# and whether the verifier failure is a FAIL_TO_PASS failure (fix wrong/incomplete) vs something else.
for t in FAILING:
    d = load(t)
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    # find the verifier FAILED test names
    vs = (d["rollout"].get("metadata") or {}).get("verifier_stdout", "") or ""
    # test names in FAIL/ERROR blocks
    fails = re.findall(r"(?:FAIL|ERROR): (\S+ \([^)]+\))", vs)
    print("="*100)
    print("TASK:", t, "reward:", (d.get("score") or {}).get("reward"))
    print("verifier failing tests:", fails[:6])
