import json, os, sys, re

TRAJ = 'trajectories'
rows = []
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith('.json'):
        continue
    d = json.load(open(os.path.join(TRAJ, fn)))
    task = fn.replace('__seed__t0.json', '')
    reward = (d.get('score') or {}).get('reward')
    meta = ((d.get('rollout') or {}).get('metadata')) or {}
    vs = meta.get('verifier_stdout', '') or ''
    has_apply = 'git apply' in vs
    rows.append((task, reward, has_apply, len(vs)))

for r in sorted(rows, key=lambda x: (x[1] or 0)):
    print(f"{r[0]:45s} r={r[1]} git_apply_in_verifier={r[2]} stdout_len={r[3]}")
