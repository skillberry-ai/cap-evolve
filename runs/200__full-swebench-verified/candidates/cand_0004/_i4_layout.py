import json, os
TRAJ = "trajectories"
fn = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(fn))
out = d.get("rollout", {}).get("output") or {}
steps = out.get("steps") or []
u = [s["message"] for s in steps if s.get("source") == "user"][0]
i = u.find("You are an expert software engineer")
# where prompt starts
print(repr(u[i-100:i+50]))
# after prompt.md, what's next
p = open("prompt.md").read().strip()
j = u.find(p) + len(p)
print("=== after prompt.md ===")
print(repr(u[j:j+800]))
