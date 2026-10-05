import json, os, sys

TRAJ = 'trajectories'
fn = os.path.join(TRAJ, 'django__django-10554__cand_0002__t0.json')
d = json.load(open(fn))
ro = d.get('rollout') or {}
steps = (ro.get('trace') or {}).get('steps') or []

# Find where the prompt.md text (expert software engineer) appears
for i, s in enumerate(steps):
    msg = s.get('message') or ''
    if 'expert software engineer' in msg:
        print(f"step {i} source={s.get('source')} contains the prompt.md text")
        print(msg[:4000])
        break
