import json, os

TRAJ = "trajectories"
# Find every command in every failing trace that hit a ModuleNotFoundError, and what
# interpreter/runner it used. This identifies the "missing deps in the interactive env"
# cluster precisely.
FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
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

for t in FAILING:
    p = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    d = json.load(open(p))
    steps = d["rollout"]["output"]["steps"]
    events = []
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            first = cmd.strip().split(" ")[0] if cmd.strip() else ""
            if "ModuleNotFoundError" in obs or "ImportError" in obs:
                mod = ""
                for line in obs.splitlines():
                    if "ModuleNotFoundError" in line or "ImportError" in line:
                        mod = line.strip()[:90]
                        break
                events.append((idx, first, mod))
    if events:
        print("##", t)
        for e in events:
            print(f"   @{e[0]} [{e[1]}] {e[2]}")
