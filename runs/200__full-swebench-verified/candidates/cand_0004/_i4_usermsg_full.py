import json, os

TRAJ = 'trajectories'
fn = os.path.join(TRAJ, 'django__django-10554__cand_0002__t0.json')
d = json.load(open(fn))
steps = (d.get('rollout') or {}).get('trace', {}).get('steps') or []
msg = steps[1].get('message') or ''
print('USER MSG LEN:', len(msg))
# check which rules are present
for marker in ['NEVER rename test functions', 'The bug exists in the current working tree',
               'When tests report NOT_FOUND', 'go test ./...', 'git diff']:
    print(f"{marker!r:60s} -> {marker in msg}")
print()
print('LAST 2500 chars of user message:')
print(msg[-2500:])
