import json, os, re

TRAJ = "trajectories"
# CURRENT passing set (this iteration's kept-good)
PASSING = [
    "django__django-12039", "django__django-12276", "django__django-13121",
    "django__django-13401", "django__django-13410", "django__django-13569",
    "django__django-14580", "django__django-15103", "django__django-15380",
    "django__django-15851", "django__django-15863", "django__django-15930",
    "matplotlib__matplotlib-22871", "matplotlib__matplotlib-24637",
    "scikit-learn__scikit-learn-25232", "sphinx-doc__sphinx-7910",
    "sphinx-doc__sphinx-8035", "sphinx-doc__sphinx-8475", "sphinx-doc__sphinx-8595",
    "sphinx-doc__sphinx-9258", "sympy__sympy-12096", "sympy__sympy-13480",
    "sympy__sympy-17139", "sympy__sympy-18211",
]
FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
    # also failing on val but not in the top-20 list:
    "pydata__xarray-6461", "pydata__xarray-6992", "pylint-dev__pylint-4661",
    "pylint-dev__pylint-4970", "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sympy__sympy-15599", "sympy__sympy-17630", "sympy__sympy-21612",
    "sympy__sympy-24213",
]

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

def cmds(task):
    d = json.load(open(os.path.join(TRAJ, f"{task}__cand_0002__t0.json")))
    steps = d["rollout"]["output"]["steps"]
    out = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            out.append(((tc.get("arguments") or {}).get("command", ""), rc, obs))
    msgs = [s.get("message") for s in steps if s.get("source") == "agent" and s.get("message")]
    final = msgs[-1] if msgs else ""
    return out, final, d

print("=== PASSING-TASK SAFETY CHECKS (blast radius) ===")
no_commit, pasted_diff, envusage = [], [], {}
for t in PASSING:
    cs, final, d = cmds(t)
    committed = any("git commit" in c for c, rc, o in cs)
    if not committed:
        no_commit.append(t)
    if re.search(r"^diff --git ", final or "", re.M):
        pasted_diff.append(t)
    # what python does the passing task use? (which interpreter is on PATH)
    py = set()
    for c, rc, o in cs:
        for m in re.findall(r"(python3?|python[0-9.]+) ", c or ""):
            py.add(m)
    envusage[t] = sorted(py)

print("passing tasks that did NOT commit:", no_commit or "NONE (all commit)")
print("passing tasks whose final message contains a pasted diff:", pasted_diff or "NONE")
print()
print("=== which python binaries passing tasks invoked ===")
for t, py in envusage.items():
    print(f"  {t:42s} {py}")
