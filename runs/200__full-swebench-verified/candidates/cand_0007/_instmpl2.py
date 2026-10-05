import json

fn = 'trajectories/pylint-dev__pylint-4661__seed__t0.json'
d = json.load(open(fn))
out = ((d.get('rollout') or {}).get('output')) or {}
extra = ((out.get('agent') or {}).get('extra')) or {}
cfg = extra.get('agent_config') or {}
it = cfg.get('instance_template', '')
print("=== chars 0-1900 of instance_template ===")
print(it[:1900])
