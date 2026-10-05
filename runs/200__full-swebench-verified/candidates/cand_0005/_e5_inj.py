import json, os

TRAJ = "trajectories"
fn = 'trajectories/django__django-10554__cand_0002__t0.json'
d = json.load(open(fn))
steps = d['rollout']['output']['steps']
u = [s["message"] for s in steps if s.get("source") == "user"][0]

prompt_md = open("prompt.md").read()
skill_md = open("SKILL.md").read()
print("prompt.md in user msg (exact):", prompt_md.strip() in u)
print("SKILL.md in user msg (exact):", skill_md.strip() in u)
i = u.find("You are an expert software engineer")
j = u.find("You can execute bash commands")
print("i:", i, "j:", j)
injected = u[i:j] if (i >= 0 and j > i) else ""
print("injected len:", len(injected), "prompt.md len:", len(prompt_md))
print("injected == prompt.md:", injected.strip() == prompt_md.strip())
# print head of user msg
print("--- head 300 ---")
print(repr(u[:300]))
print("--- between issue-end and injected start ---")
if i > 0:
    print(repr(u[max(0,i-200):i]))
