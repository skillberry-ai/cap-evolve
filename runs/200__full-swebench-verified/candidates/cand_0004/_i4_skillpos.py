import json, os
TRAJ = "trajectories"
fn = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(fn))
out = d.get("rollout", {}).get("output") or {}
steps = out.get("steps") or []
u = [s["message"] for s in steps if s.get("source") == "user"][0]
# where is SKILL.md content relative to the instance template?
i_skill = u.find("You are an expert software engineer")
i_issue = u.find("Please solve this issue")
i_bash = u.find("You can execute bash commands")
print(f"issue starts at {i_issue}, skill at {i_skill}, bash template at {i_bash}")
# So layout = "Please solve this issue: <issue> \n\n <SKILL.md>\n\n\n <instance template>"
# Find what's between issue end and skill start
j = u.find("You are an expert")
print("between issue and skill:", repr(u[j-200:j]))
# after skill
p = open("prompt.md").read().strip()
k = u.find(p) + len(p)
print("after prompt.md:", repr(u[k:k+300]))
