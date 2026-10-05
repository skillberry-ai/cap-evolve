import json, os
TRAJ = "trajectories"
def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None
d = load("django__django-16667")
out = (d.get("rollout") or {}).get("output") or {}
steps = out.get("steps") or []
u = [s["message"] for s in steps if s.get("source") == "user"][0]
# print issue text (before the injected skill)
i = u.find("You are an expert software engineer")
print(u[:i])
