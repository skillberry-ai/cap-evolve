import json, os, sys, re

TRAJ = 'trajectories'
task = sys.argv[1]
fn = [f for f in os.listdir(TRAJ) if f.startswith(task)][0]
d = json.load(open(os.path.join(TRAJ, fn)))
meta = ((d.get('rollout') or {}).get('metadata')) or {}
vs = meta.get('verifier_stdout', '') or ''
idx = vs.find('SWEBench results starts here')
head = vs[:idx] if idx >= 0 else vs
lines = head.splitlines()
# find lines that mention running the test command or the module being invoked
for i, l in enumerate(lines):
    if 'runtests' in l or 'Importing application' in l or 'Testing against' in l:
        print(l[:200])
# count test result lines vs total
n_ok = sum(1 for l in lines if l.endswith(' ... ok'))
print('n ok lines:', n_ok)
