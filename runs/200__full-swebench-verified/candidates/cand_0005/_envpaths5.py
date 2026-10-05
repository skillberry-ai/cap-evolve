import json, os

TRAJ = "trajectories"
# Tracebacks from failed agent `python` runs: which site-packages path appears?
hits = {}
for f in sorted(os.listdir(TRAJ)):
    if not f.endswith(".json"):
        continue
    task = f.split("__")[0]
    d = json.load(open(os.path.join(TRAJ, f)))
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    for s in steps:
        obs = s.get("observation") or {}
        for r in (obs.get("results") or []):
            try:
                j = json.loads(r.get("content", ""))
                o = j.get("output", "") or ""
                for ln in o.splitlines():
                    if ln.strip().startswith("File") and "/miniconda3/" in ln:
                        p = ln.split('"')[1] if '"' in ln else ln
                        key = "base" if "/miniconda3/lib/" in p else ("envs/testbed" if "envs/testbed" in p else "other")
                        hits.setdefault(key, set()).add(p.split("/lib/")[0])
            except Exception:
                pass
for k, v in hits.items():
    print(k, ":", sorted(v))
