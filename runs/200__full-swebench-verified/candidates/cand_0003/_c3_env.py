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

# What python environment do the agents see? Show outputs of env probes.
# And how do PASSING tasks' final commits look — do they include test-file changes?
for task in ["django__django-13569", "django__django-15863", "sphinx-doc__sphinx-8595", "sympy__sympy-13480"]:
    d = load(task)
    out = ((d.get("rollout") or {}).get("output")) or {}
    steps = out.get("steps") or []
    print("=" * 110)
    print(task)
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            if re.search(r"(which |conda info|conda env|/opt/miniconda|pip install|pip show)", c):
                print(f"  step {i}: {c.splitlines()[0][:130]}")
                tail = (obs or "")[:300]
                for l in tail.splitlines()[:6]:
                    print(f"     | {l[:140]}")
