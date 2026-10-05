import json, os

TRAJ = "trajectories"
# Check: does `python -c "import django"` (agent's interpreter) resolve django from /testbed?
# Look at successful agent python commands importing the repo package and print resolution.
for f in ["django__django-15930__seed__t0.json", "django__django-13401__seed__t0.json", "sympy__sympy-17139__seed__t0.json", "pydata__xarray-6992__seed__t0.json"]:
    d = json.load(open(os.path.join(TRAJ, f)))
    steps = d["rollout"].get("trace") or {}
    steps = steps.get("steps") or []
    for s in steps:
        if s.get("source") != "agent":
            continue
        obs = s.get("observation") or {}
        for r in (obs.get("results") or []):
            try:
                j = json.loads(r.get("content", ""))
                o = (j.get("output", "") or "")
                if "ModuleNotFoundError" in o:
                    ln = [l for l in o.splitlines() if "File" in l and "/testbed" in l]
                    if ln:
                        print(f.split("__")[0], "->", ln[0].strip()[:150])
            except Exception:
                pass
