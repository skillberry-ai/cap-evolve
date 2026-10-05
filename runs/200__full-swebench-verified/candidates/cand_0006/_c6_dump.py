import json, os, glob

TRAJ = "trajectories"

# Failing tasks (excluding infra-errored which have 0 steps)
FAILING = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555",
    "django__django-12325", "django__django-12708", "django__django-14007",
    "django__django-14376", "django__django-15629", "django__django-16032",
    "django__django-16667",
]
# also other 0.0 tasks present in trajectories (from full val set)
EXTRA = [
    "pydata__xarray-6461", "pydata__xarray-6992", "pylint-dev__pylint-4661",
    "pylint-dev__pylint-4970", "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sympy__sympy-15599", "sympy__sympy-17630", "sympy__sympy-21612", "sympy__sympy-24213",
]
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

def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

def agent_commands(d):
    """Extract (idx, command, obs_output, returncode) for each agent step."""
    steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
    out = []
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        cmd = None
        for tc in (s.get("tool_calls") or []):
            a = (tc.get("arguments") or {})
            cmd = a.get("command")
        # observation comes from the NEXT user step (or the same dict?)
        out.append((idx, s, cmd))
    return out

def obs_after(steps, idx):
    """Return observation content for the agent step at index idx (look at following user step)."""
    for j in range(idx + 1, min(idx + 3, len(steps))):
        s = steps[j]
        if s.get("source") == "user" or s.get("role") == "user":
            ob = s.get("observation")
            if ob:
                try:
                    c = ob["results"][0]["content"]
                    jj = json.loads(c)
                    return jj.get("output", ""), jj.get("returncode")
                except Exception:
                    return None, None
            return s.get("message", ""), None
    return None, None

if __name__ == "__main__":
    import sys
    which = sys.argv[1] if len(sys.argv) > 1 else "failing"
    tasks = FAILING if which == "failing" else (EXTRA if which == "extra" else PASSING)
    for t in tasks:
        try:
            d = load(t)
        except FileNotFoundError:
            print(f"!! no trace for {t}")
            continue
        steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
        print(f"\n===================== {t} ({len(steps)} steps) =====================")
        for idx, s, cmd in agent_commands(d):
            if cmd is None:
                continue
            obs, rc = obs_after(steps, idx)
            obs_head = (obs or "")[:160].replace("\n", " | ")
            print(f"[{idx:3d}] rc={rc} $ {cmd[:200]}")
            print(f"      OBS: {obs_head}")
