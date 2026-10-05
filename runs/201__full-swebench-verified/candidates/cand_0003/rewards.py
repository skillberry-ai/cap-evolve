import json, os

TRAJ = 'trajectories'
rows = []
for f in sorted(os.listdir(TRAJ)):
    if not f.endswith('.json'):
        continue
    d = json.load(open(os.path.join(TRAJ, f)))
    r = d['rollout']
    sc = d.get('score', {})
    reward = sc.get('reward')
    task = r.get('task_id')
    err = r.get('error')
    steps = 0
    trace = r.get('trace') or r.get('output') or {}
    steps = len(trace.get('steps', []))
    rows.append((task, reward, steps, bool(err)))

rows.sort(key=lambda x: (x[1] is not None, x[1] or 0))
for task, reward, steps, err in rows:
    print(f'{reward!s:>5}  steps={steps:<4} err={err!s:<5} {task}')
