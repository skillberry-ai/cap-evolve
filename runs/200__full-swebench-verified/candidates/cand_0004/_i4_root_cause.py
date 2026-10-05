import json, os, re
TRAJ = "trajectories"

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

def steps_of(task):
    d = load(task)
    out = (d.get("rollout") or {}).get("output") or {}
    return out.get("steps") or []

# What is the ACTUAL root cause per failing task?
# 1. astropy-13453: patch called self.data._set_col_formats() but HTMLData has no cols attr → wrong API usage; also NEVER ran tests (repro failed w/ erfa missing)
# 2. django-10554: verifier says ORDER BY term does not match any column in the result set — union ordering issue; patch cloned queries. Wrong approach.
# 3. django-11555: OrderBy object has no attribute 'split' — patch to get_order_dir was incomplete; the real fix must handle OrderBy in find_ordering_name.
# 4. django-12325: ImproperlyConfigured parent_link — agent edited the wrong logic (ModelBase._prepare instead of Options._prepare? no, options.py line 256)
# 5. django-12708: wrong number (2) of constraints — patch insufficient
# 6. django-14007: AutoField object has no attribute output_field — patch incomplete (needs converters handling for AutoFieldMetaClass?)
# 7. django-14376: deprecatedoptiondbname vs optiondbname — the fix passed wrong database name. The kwargs 'database' rename was wrong: gold is about OPTIONS taking precedence
# 8. django-15629: None != 'nocase' collation — patch didn't propagate collation to FK
# 9. django-16032: sub-select returns N columns — patch on related_lookups insufficient
# 10. django-16667: '9223372036854775808-12-1' != '0-0-0' — agent caught OverflowError but then returned the raw string instead of "0-0-0"

# Common denominators:
# A. NO test ran successfully in ANY failing task: pytest not found (rc=127), imports fail (asgiref/docutils/mpmath/erfa missing).
# B. The agent never gets feedback that its patch is wrong before submitting.
# C. Each patch is close but subtly wrong — the exact issue the failing test exposes.

# Question: can the agent actually run tests in this environment? The verifier runs them AFTER.
# The verifier runs: git checkout of test files + apply test patch + runtests.py style commands.
# For django the verifier ran e.g. tests/runtests.py — check the verifier command for 16667.
d = load("django__django-16667")
vs = ((d.get("rollout") or {}).get("metadata") or {}).get("verifier_stdout", "")
print(vs[:100])
