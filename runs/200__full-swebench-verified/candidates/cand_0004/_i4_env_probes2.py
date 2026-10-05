import json, os

TRAJ = 'trajectories'

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + '__'):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# What did the agent see for `which python`, `python -V`? Look for env probing commands in all traces.
import re
probes = {}
for f in sorted(os.listdir(TRAJ)):
    if not f.endswith('.json'):
        continue
    d = json.load(open(os.path.join(TRAJ, f)))
    ro = d.get('rollout')
    if not ro:
        continue
    tr = ro.get('trace') or {}
    steps = tr.get('steps') or []
    for s in steps:
        if s.get('source') != 'agent':
            continue
        for tc in (s.get('tool_calls') or []):
            c = (tc.get('arguments') or {}).get('command', '')
            if any(k in c for k in ('which python', 'python -V', 'python --version', 'conda', 'echo $PATH', 'printenv')):
                probes.setdefault(f, []).append(c[:120])

for k in list(probes)[:5]:
    print(k, '->', probes[k][:4])
print('total tasks with env probes:', len(probes))
