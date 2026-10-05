import json

d = json.load(open('trajectories/django__django-10554__cand_0002__t0.json'))
r = d['rollout']
out = r.get('output') or {}
agent = out.get('agent') or {}
extra = agent.get('extra') or {}
cfg = extra.get('agent_config') or {}
print(cfg.get('instance_template'))
