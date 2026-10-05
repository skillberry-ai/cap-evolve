import json, sys, os

TRAJ = 'trajectories'
fn = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, fn)))
out = ((d.get('rollout') or {}).get('output')) or {}
steps = out.get('steps') or []
s = steps[int(sys.argv[2])]
print('keys:', list(s.keys()))
print(json.dumps(s, indent=1)[:4000])
