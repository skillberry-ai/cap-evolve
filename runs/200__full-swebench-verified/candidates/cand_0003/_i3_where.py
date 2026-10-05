import json

d = json.load(open('trajectories/django__django-16667__cand_0002__t0.json'))
r = d['rollout']
out = r.get('output') or {}
agent = out.get('agent') or {}
extra = agent.get('extra') or {}
cfg = extra.get('agent_config') or {}
it = cfg.get('instance_template', '')
skill_txt = open('SKILL.md').read()
prompt_txt = open('prompt.md').read()
print('SKILL.md first 80 chars in instance_template:', skill_txt[:80] in it)
print('prompt.md first 80 chars in instance_template:', prompt_txt[:80] in it)
# search all steps' user messages for prompt.md content
steps = (r.get('trace') or {}).get('steps') or []
for s in steps:
    if s.get('source') == 'user':
        m = s.get('message', '')
        print('user msg contains prompt.md head:', prompt_txt[:80] in m)
        print('user msg contains SKILL.md head:', skill_txt[:80] in m)
        break
