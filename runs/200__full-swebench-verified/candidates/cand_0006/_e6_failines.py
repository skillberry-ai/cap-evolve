import json, os, sys, subprocess

TRAJ = 'trajectories'
fn = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, fn)))
md = d['rollout'].get('metadata') or {}
vs = md.get('verifier_stdout', '') or ''
# Find the failure summary section: lines between "=====" markers or FAILED lines
lines = vs.splitlines()
# print everything that looks like a failure report
out = []
keep = False
for i, l in enumerate(lines):
    if ('FAIL' in l or 'ERROR' in l or 'Traceback' in l or '=====' in l or 'assert' in l.lower() or 'Error' in l):
        # print context
        out.append(f"{i}: {l}")
print('\n'.join(out[:80]))
