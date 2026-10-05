import json, os

TRAJ = 'trajectories'
fn = os.path.join(TRAJ, 'django__django-10554__cand_0002__t0.json')
d = json.load(open(fn))
steps = (d.get('rollout') or {}).get('trace', {}).get('steps') or []
msg = steps[1].get('message') or ''
# Find the region between the issue and the instance template
i0 = msg.find('You are an expert software engineer')
print("=== prompt.md region (chars from issue-prompt boundary) ===")
print(msg[i0:i0+5800])
