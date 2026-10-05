import json, os, sys, re

TRAJ = 'trajectories'

# For every failing task: find FAIL/ERROR test names in verifier output (pytest-style FAILED lines too)
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith('.json'):
        continue
    d = json.load(open(os.path.join(TRAJ, fn)))
    task = fn.replace('__seed__t0.json', '')
    reward = (d.get('score') or {}).get('reward')
    if reward != 0.0:
        continue
    meta = ((d.get('rollout') or {}).get('metadata')) or {}
    vs = meta.get('verifier_stdout', '') or ''
    idx = vs.find('SWEBench results starts here')
    head = vs[:idx] if idx >= 0 else vs
    lines = head.splitlines()
    print('=' * 20, task, '=' * 20)
    for l in lines:
        if l.startswith('ERROR:') or l.startswith('FAIL:') or l.startswith('FAILED '):
            print('  ', l[:170])
        if re.match(r'^Ran \d+ tests', l) or l.startswith('FAILED (') or l == 'OK':
            print('  SUM:', l[:120])
