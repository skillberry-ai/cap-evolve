import json, os, re

TRAJ = 'trajectories'

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + '__'):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# What does the harness do to extract the model patch? Check rollout 'output' notes / final_metrics
d = load('django__django-16667')
out = (d.get('rollout') or {}).get('output') or {}
print('notes:', json.dumps(out.get('notes'))[:2000])
print('final_metrics:', json.dumps(out.get('final_metrics'))[:800])
# also check 'input' field
inp = d.get('input')
print('INPUT keys:', list(inp.keys()) if isinstance(inp, dict) else type(inp))
if isinstance(inp, dict):
    for k in inp:
        v = inp[k]
        print('---', k, '---')
        print(str(v)[:400])
