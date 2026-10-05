import json

fn = 'trajectories/pylint-dev__pylint-4661__cand_0002__t0.json'
d = json.load(open(fn))
out = ((d.get('rollout') or {}).get('output')) or {}
extra = ((out.get('agent') or {}).get('extra')) or {}
cfg = extra.get('agent_config') or {}
it = cfg['instance_template']
st = cfg['system_template']
print("=== INSTANCE TEMPLATE (full) ===")
print(it)
print("=== SYSTEM TEMPLATE (full) ===")
print(st)
