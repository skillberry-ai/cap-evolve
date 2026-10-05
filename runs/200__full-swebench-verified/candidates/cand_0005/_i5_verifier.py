import json, os, sys

TRAJ = "trajectories"
INFRA = {"django__django-13809", "django__django-15280", "django__django-15741", "django__django-16485",
         "sphinx-doc__sphinx-8638", "sphinx-doc__sphinx-9367"}

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

def cmd_of(s):
    for tc in (s.get("tool_calls") or []):
        return (tc.get("arguments") or {}).get("command", "")
    return ""

# For each failing (non-infra) task: dump the verifier stdout tail + the last few agent commands + final message
targets = [
    "astropy__astropy-13453", "django__django-10554", "django__django-11555", "django__django-12325",
    "django__django-12708", "django__django-14007", "django__django-14376", "django__django-15629",
    "django__django-16032", "django__django-16667", "pydata__xarray-6461", "pydata__xarray-6992",
    "pylint-dev__pylint-4661", "pylint-dev__pylint-4970", "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sympy__sympy-15599", "sympy__sympy-17630", "sympy__sympy-21612", "sympy__sympy-24213",
]

mode = sys.argv[1] if len(sys.argv) > 1 else "verifier"

for task in targets:
    d = load(task)
    if d is None:
        print(f"!! no trace for {task}")
        continue
    md = (d.get("rollout") or {}).get("metadata") or {}
    vs = md.get("verifier_stdout", "") or ""
    print("=" * 100)
    print(f"### {task}")
    if mode == "verifier":
        lines = vs.splitlines()
        # show the tail: test summary lines
        print(f"[verifier stdout: {len(vs)} chars, {len(lines)} lines]")
        for l in lines[-45:]:
            print("  |", l[:180])
    elif mode == "tail":
        steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
        agent_steps = [s for s in steps if s.get("source") == "agent"]
        for s in agent_steps[-6:]:
            c = cmd_of(s)
            obs, rc = obs_of(s)
            print(f"--- rc={rc} CMD: {c[:220]}")
            for l in (obs or "").splitlines()[-6:]:
                print("    |", l[:170])
        # final assistant message
        if agent_steps:
            print("FINAL MSG:", (agent_steps[-1].get("message") or "")[:500])
