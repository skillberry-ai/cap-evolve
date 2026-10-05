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
# find the FAILED / OK summary lines
for i, l in enumerate(lines):
    if re.search(r'^(FAILED|OK|Ran \d+ tests|ERROR:|FAIL:)', l):
        print(l[:200])
# also print around the test failure sections
print('----- test result section -----')
# print lines that contain 'FAIL:'/'ERROR:' with 3 lines after
for i, l in enumerate(lines):
    if l.startswith('ERROR:') or l.startswith('FAIL:'):
        print('\n'.join(lines[i:i+8]))
        print('...')
