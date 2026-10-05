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
# find which test module(s) were run — look for lines mentioning "test_" module labels (django test style)
mods = []
for l in lines:
    m = re.match(r'^test_\w+ \(([\w.]+)\)', l)
    if m:
        mods.append(m.group(1))
seen = []
for m in mods:
    if m not in seen:
        seen.append(m)
print('distinct test classes run:', len(seen))
for s in seen[:40]:
    print(' ', s)
# Also print summary lines
print('--- summary ---')
for l in lines:
    if re.match(r'^(Ran |OK|FAILED|ERROR:|FAIL:)', l):
        print(l)
