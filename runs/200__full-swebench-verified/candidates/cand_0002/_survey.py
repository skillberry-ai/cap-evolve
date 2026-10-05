import json, sys, os, re

TRAJ = 'trajectories'
rows = []
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith('.json'):
        continue
    d = json.load(open(os.path.join(TRAJ, fn)))
    sc = d.get('score', {})
    task = fn.replace('__seed__t0.json', '')
    out = ((d.get('rollout') or {}).get('output')) or {}
    steps = out.get('steps') or []
    final = ''
    ncmd = 0
    for s in steps:
        msg = s.get('message', '')
        if isinstance(msg, str) and s.get('source') == 'agent':
            final = msg
            if 'COMPLETE_TASK' in msg:
                ncmd += 1
    err = (d.get('rollout') or {}).get('error')
    rows.append((task, sc.get('reward'), len(steps), ncmd, err, final[:130].replace('\n', ' ')))

for r in sorted(rows, key=lambda x: (x[1] if x[1] is not None else -1)):
    print(f"{r[0]:45s} reward={r[1]} steps={r[2]:3d} submits={r[3]} err={str(r[4])[:40]}")
    print(f"    final: {r[5]}")
