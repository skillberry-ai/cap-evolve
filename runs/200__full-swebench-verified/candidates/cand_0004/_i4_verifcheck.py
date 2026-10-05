import json, os
TRAJ = "trajectories"
# Check which version got injected into the user message for cand_0002
fn = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(fn))
out = d.get("rollout", {}).get("output") or {}
steps = out.get("steps") or []
u = [s["message"] for s in steps if s.get("source") == "user"][0]
p = open("prompt.md").read()
s = open("SKILL.md").read()
# Find the "Critical rules" section in u
i = u.find("## Critical rules")
print("crit rules found at", i)
tail = u[i:i+2500]
print(tail)
