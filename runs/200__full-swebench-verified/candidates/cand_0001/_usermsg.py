import json, os

TRAJ = "trajectories"
d = json.load(open(os.path.join(TRAJ, "django__django-10554__seed__t0.json")))
steps = d["rollout"]["output"]["steps"]
user_msgs = [s["message"] for s in steps if s.get("source") == "user"]
print("N user msgs:", len(user_msgs))
u = user_msgs[0]
print("LEN:", len(u))
print(u[:600])
print("...")
# check for the 5 extra rules that exist in prompt.md but not SKILL.md
for marker in [
    "NEVER rename test functions",
    "git diff MUST show actual changes",
    "do NOT assume they are",
    "may require fixes across multiple files",
    "Avoid restructuring code, inlining functions",
]:
    print(f"contains {marker!r}:", marker in u)
print()
print("TAIL 1500:")
print(u[-1500:])
