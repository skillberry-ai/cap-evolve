import json, os
TRAJ = 'trajectories'

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + '__'):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

for task in ['django__django-16667', 'astropy__astropy-13453', 'sphinx-doc__sphinx-7910']:
    d = load(task)
    steps = (d.get('rollout') or {}).get('trace', {}).get('steps') or []
    msg = steps[1].get('message') or ''
    print(task, 'len', len(msg), '| NEVER-rename present:', 'NEVER rename test functions' in msg,
          '| go test rule:', 'go test' in msg, '| count "expert software engineer":', msg.count('expert software engineer'))
