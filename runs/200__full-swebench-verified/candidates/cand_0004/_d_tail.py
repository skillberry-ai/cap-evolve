import json, os, sys

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

task = sys.argv[1] if len(sys.argv) > 1 else "astropy__astropy-13453"
d = load(task)
r = d["rollout"]
print("score:", json.dumps(d.get("score"))[:600])
out = r["output"]
print("final_metrics:", json.dumps(out.get("final_metrics"))[:800])
print("notes:", json.dumps(out.get("notes"))[:600])
print("error:", json.dumps(r.get("error"))[:400])
print("cost_usd:", r.get("cost_usd"))
steps = out["steps"]
print("n steps:", len(steps))
for s in steps[-10:]:
    m = s.get("message") or {}
    src = s.get("source")
    c = m.get("content") if isinstance(m, dict) else m
    print("===", src, str(c)[:500].replace("\n", " | "))
