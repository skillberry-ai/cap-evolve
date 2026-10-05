import json, os, sys

TRAJ = 'trajectories'
fn = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, fn)))
out = d['rollout']['output']
agent = out.get('agent') or {}
extra = agent.get('extra') or {}
cfg = extra.get('agent_config') or {}
it = cfg.get('instance_template') or ''
print(it)
