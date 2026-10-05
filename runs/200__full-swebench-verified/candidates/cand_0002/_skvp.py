import json

d = json.load(open('trajectories/django__django-10554__seed__t0.json'))
r = d['rollout']
# The instance_template contains {{task}} - check where prompt.md is injected.
# The user message = issue + prompt.md + "You can execute bash commands..." template.
# So prompt.md is injected INTO the instance template between {{task}} and the bash section.
# Q: is SKILL.md == prompt.md? Compare.
skill = open('SKILL.md').read()
prompt = open('prompt.md').read()
print("SKILL.md == prompt.md:", skill == prompt)
print("SKILL.md len:", len(skill), "prompt.md len:", len(prompt))
steps = r['trace']['steps']
u = steps[1]['message']
print("skill content in user msg:", skill.strip() in u)
print("prompt content in user msg:", prompt.strip() in u)
