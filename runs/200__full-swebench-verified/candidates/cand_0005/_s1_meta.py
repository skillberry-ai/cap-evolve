import json, os, sys

TRAJ = 'trajectories'
rows = []
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith('.json'):
        continue
    task = fn.replace('__cand_0002__t0.json', '')
    d = json.load(open(os.path.join(TRAJ, fn)))
    sc = d.get('score') or {}
    ro = d.get('rollout') or {}
    out = ro.get('output') or {}
    steps = out.get('steps') or []
    md = ro.get('metadata') or {}
    rows.append((task, sc.get('reward'), len(steps), md))

# look for what's in metadata
r = rows[0]
print(json.dumps(r[3], indent=1)[:4000])
