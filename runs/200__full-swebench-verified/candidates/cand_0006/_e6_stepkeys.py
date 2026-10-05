import json, os, sys

TRAJ = 'trajectories'
fn = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, fn)))
out = d['rollout']['output']
steps = out['steps']

# The ATIF conversion may hide tool calls. Look for raw fields on each step.
for s in steps:
    print(f"step {s.get('step_id')} [{s.get('source')}] keys={sorted(s.keys())}")
    if s.get('step_id', 0) > 8:
        break
