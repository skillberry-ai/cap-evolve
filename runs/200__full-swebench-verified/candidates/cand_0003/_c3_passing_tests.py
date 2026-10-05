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

# How did PASSING tasks run tests successfully? Find the first test command that
# actually produced test output (passed/failed summary).
PASSING = [
    "django__django-12039","django__django-12276","django__django-13121","django__django-13401",
    "django__django-13410","django__django-13569","django__django-14580","django__django-15103",
    "django__django-15380","django__django-15851","django__django-15863","django__django-15930",
    "matplotlib__matplotlib-22871","matplotlib__matplotlib-24637","pydata__xarray-6461",
    "scikit-learn__scikit-learn-25232","sphinx-doc__sphinx-7910","sphinx-doc__sphinx-8035",
    "sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595","sphinx-doc__sphinx-9258","sympy__sympy-12096",
    "sympy__sympy-13480","sympy__sympy-17139","sympy__sympy-18211",
]

for task in PASSING:
    d = load(task)
    out = ((d.get("rollout") or {}).get("output")) or {}
    steps = out.get("steps") or []
    found = []
    env_probes = []
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            if re.search(r"(pytest|py\.test|runtests\.py|python.* -m pytest)", c) and not c.startswith(("grep", "cat ", "ls")):
                ok = re.search(r"(\d+ (passed|failed)|Ran \d+ tests|^OK)", obs or "", re.M)
                found.append((i, rc, c.splitlines()[0][:130], bool(ok)))
            if re.search(r"(which python|conda|env |printenv|echo \$PATH|ls /opt)", c):
                env_probes.append((i, c.splitlines()[0][:100]))
    print("=" * 110)
    print(task, "reward", d["score"]["reward"])
    for (i, rc, one, ok) in found:
        print(f"  {'TESTOK' if ok else '     '} step {i:3d} rc={rc}: {one}")
