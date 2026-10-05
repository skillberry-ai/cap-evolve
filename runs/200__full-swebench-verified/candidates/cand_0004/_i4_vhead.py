import json, os

TRAJ = 'trajectories'

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + '__'):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# Check the verifier: does it use a special conda env (/opt/miniconda3/envs/testbed)?
# And check what python the agent had: which python, PATH etc.
d = load('django__django-16667')
meta = ((d.get('rollout') or {}).get('metadata')) or {}
vs = meta.get('verifier_stdout', '') or ''
print('VERIFIER first 40 lines:')
for l in vs.splitlines()[:40]:
    print('  ', l[:180])
