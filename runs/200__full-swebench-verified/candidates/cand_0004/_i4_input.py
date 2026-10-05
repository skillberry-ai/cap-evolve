import json, os
TRAJ = 'trajectories'
d = json.load(open(os.path.join(TRAJ, 'django__django-16667__cand_0002__t0.json')))
inp = d.get('input')
print(repr(inp)[:800] if inp else 'EMPTY')
