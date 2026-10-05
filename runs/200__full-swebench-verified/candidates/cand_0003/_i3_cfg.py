import json

d = json.load(open('trajectories/django__django-10554__cand_0002__t0.json'))
r = d['rollout']
out = r.get('output') or {}
agent = out.get('agent') or {}
extra = agent.get('extra') or {}
cfg = extra.get('agent_config') or {}
for k, v in cfg.items():
    s = v if isinstance(v, str) else json.dumps(v)
    print(f'--- {k} ({len(s)} chars) ---')
    print(s[:400])
    print()
