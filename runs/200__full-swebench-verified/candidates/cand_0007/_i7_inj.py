import json, os

TRAJ = "trajectories"
d = json.load(open(os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")))
u = [s["message"] for s in d["rollout"]["output"]["steps"] if s.get("source") == "user"][0]

prompt_md = open("prompt.md").read()
skill_md = open("SKILL.md").read()

print("prompt.md in user msg (exact):", prompt_md.strip() in u)
print("SKILL.md in user msg (exact):", skill_md.strip() in u)
i = u.find("You are an expert software engineer")
j = u.find("You can execute bash commands and edit files")
injected = u[i:j]
print("injected len:", len(injected), "prompt.md len:", len(prompt_md))
print("injected == prompt.md:", injected.strip() == prompt_md.strip())
