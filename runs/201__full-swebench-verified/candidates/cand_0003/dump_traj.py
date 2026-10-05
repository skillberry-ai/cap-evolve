import json, sys, os, re

TRAJ = 'trajectories'
task = sys.argv[1]
d = json.load(open(f'{TRAJ}/{task}__seed__t0.json'))
r = d['rollout']
trace = r.get('trace') or r.get('output')
steps = trace['steps']
print('N steps:', len(steps))
for s in steps:
    src = s.get('source', '?')
    msg = s.get('message', '') or ''
    extra = {k: v for k, v in s.items() if k not in ('step_id', 'source', 'message')}
    if not isinstance(msg, str):
        msg = json.dumps(msg)
    print(f"===== step {s.get('step_id')} [{src}] extra_keys={list(extra.keys())} =====")
    print(msg[:1800])
    for k, v in extra.items():
        vs = v if isinstance(v, str) else json.dumps(v)
        print(f"  -- {k}: {vs[:600]}")
    print()
