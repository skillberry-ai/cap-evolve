import json
fn = 'trajectories/django__django-10554__cand_0002__t0.json'
d = json.load(open(fn))
out = d['rollout']['output']
cfg = out['agent']['extra']['agent_config']
print('CONFIG KEYS:', list(cfg.keys()))
for k, v in cfg.items():
    print(f'--- {k} (len {len(v) if isinstance(v,str) else "obj"}) ---')
    if isinstance(v, str):
        print(v[:6000])
        print()
