import json, os
TRAJ = "trajectories"
fn = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(fn))
out = d.get("rollout", {}).get("output") or {}
steps = out.get("steps") or []
for s in steps[:3]:
    print("---", s.get("source"), "---")
    print(repr((s.get("message") or "")[:120]))
# is there any place SKILL.md content is the SYSTEM message?
syss = [s for s in steps if s.get("source") == "system"]
print("n system messages:", len(syss))
