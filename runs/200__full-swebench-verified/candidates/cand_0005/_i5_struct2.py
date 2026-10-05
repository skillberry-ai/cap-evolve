import json, os, sys

TRAJ = "trajectories"

def load(task_prefix):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task_prefix + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

d = load("django__django-10554")
r = d.get("rollout") or {}
steps = (r.get("output") or {}).get("steps") or []
print("output.steps:", len(steps))
if steps:
    for s in steps[:3]:
        print("keys:", list(s.keys()), "source:", s.get("source"))
    # find an agent step with tool_calls
    for s in steps:
        if s.get("source") == "agent":
            print(json.dumps(s, indent=1)[:1500])
            break
    # observation step
    for s in steps:
        if s.get("source") != "agent" and s.get("observation"):
            print("OBS:", json.dumps(s, indent=1)[:800])
            break

md = r.get("metadata") or {}
print("metadata keys:", list(md.keys()))
tc = r.get("tool_calls")
print("rollout.tool_calls type:", type(tc), (len(tc) if isinstance(tc, list) else tc))
