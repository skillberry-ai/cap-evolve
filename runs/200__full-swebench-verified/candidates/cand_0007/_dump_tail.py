import json, sys, os

TRAJ = 'trajectories'
fn = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, fn)))
out = ((d.get('rollout') or {}).get('output')) or {}
steps = out.get('steps') or []

# mini-swe-agent format: steps have step_id, source, message.
# agent messages contain the command in a specific format. Let's print last 8 steps raw.
for s in steps[-int(sys.argv[2] if len(sys.argv) > 2 else 8):]:
    print('=' * 25, 'step', s.get('step_id'), 'source', s.get('source'), '=' * 25)
    msg = s.get('message', '')
    if isinstance(msg, dict):
        msg = json.dumps(msg, indent=1)
    print(str(msg)[:3500])
    print()
