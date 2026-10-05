import json, os, re, sys

TRAJ = 'trajectories'
task = sys.argv[1]
fn = [f for f in os.listdir(TRAJ) if f.startswith(task)][0]
d = json.load(open(os.path.join(TRAJ, fn)))
meta = ((d.get('rollout') or {}).get('metadata')) or {}
vs = meta.get('verifier_stdout', '') or ''
# Find where the verifier applies the patch / resets. Look for 'git' lines in verifier stdout
for line in vs.splitlines():
    if re.search(r'git |Updated \d+ path|reset|checkout|apply|patch', line, re.I):
        print(line[:250])
