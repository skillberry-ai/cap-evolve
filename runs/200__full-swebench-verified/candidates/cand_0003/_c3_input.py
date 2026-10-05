import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

d = load("django__django-12039")
inp = d.get("input") or {}
print("input keys:", list(inp.keys()))
for k, v in inp.items():
    s = json.dumps(v) if not isinstance(v, str) else v
    print(f"--- {k} (len {len(s)}) ---")
    print(s[:600])
ro = d["rollout"]
print("task_id:", ro.get("task_id"))
tr = ro.get("trace") or {}
print("trace keys:", list(tr.keys()))
tc = ro.get("tool_calls")
print("tool_calls type:", type(tc), "len:", len(tc) if tc else 0)
if tc:
    print("first 3:", json.dumps(tc[:3])[:800])
