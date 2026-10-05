import json, os, re, sys

TRAJ = 'trajectories'
task = sys.argv[1]
fn = [f for f in os.listdir(TRAJ) if f.startswith(task)][0]
d = json.load(open(os.path.join(TRAJ, fn)))
meta = ((d.get('rollout') or {}).get('metadata')) or {}
vs = meta.get('verifier_stdout', '') or ''
idx = vs.find('SWEBench results starts here')
head = vs[:idx] if idx >= 0 else vs
lines = head.splitlines()
# The FIRST ~60 lines: the test commands and reset flow
print('\n'.join(lines[:60]))
