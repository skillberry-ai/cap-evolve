import json, os, sys

TRAJ = 'trajectories'

# Extract all commands run per task, for quick clustering
fn = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, fn)))
out = d['rollout']['output']
steps = out['steps']
for s in steps:
    if s.get('source') != 'agent':
        continue
    for c in (s.get('tool_calls') or []):
        args = c.get('arguments') or c.get('input') or {}
        cmd = args.get('command') if isinstance(args, dict) else None
        if cmd:
            print(f"[{s.get('step_id')}] {cmd[:200]}")
