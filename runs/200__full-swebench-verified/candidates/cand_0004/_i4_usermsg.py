import json, os
TRAJ = "trajectories"
fn = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(fn))
out = d.get("rollout", {}).get("output") or {}
steps = out.get("steps") or []
u = [s["message"] for s in steps if s.get("source") == "user"][0]
prompt_md = open("prompt.md").read()
skill_md = open("SKILL.md").read()
print("prompt.md exact in user msg:", prompt_md.strip() in u)
print("SKILL.md exact in user msg:", skill_md.strip() in u)
i = u.find("You are an expert software engineer")
print("expert prefix idx:", i)
print("user msg head:", repr(u[:200]))
print("user msg len:", len(u))
# print the tail of the user message
print("user msg tail:", repr(u[-1500:]))
