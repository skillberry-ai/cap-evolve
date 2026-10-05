import json, os, sys

TRAJ = 'trajectories'
fn = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, fn)))
out = d['rollout']['output']
agent = out.get('agent') or {}
extra = agent.get('extra') or {}
cfg = extra.get('agent_config') or {}
print("agent_config keys:", list(cfg.keys()))
for k, v in cfg.items():
    if isinstance(v, str):
        print(f"--- {k} (len {len(v)}) ---")
        print(v[:1200])
        print("..." if len(v) > 1200 else "")
    else:
        print(f"--- {k} ---")
        print(json.dumps(v)[:800])
