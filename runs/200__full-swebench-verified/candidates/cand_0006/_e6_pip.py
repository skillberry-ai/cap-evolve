import json, os, sys, re

TRAJ = 'trajectories'
ALL = sorted(f for f in os.listdir(TRAJ) if f.endswith('.json'))
print(f"{'task':45s} {'r':5s} {'pip-install':10s} {'testcmds-run':12s}")
for fn in ALL:
    d = json.load(open(os.path.join(TRAJ, fn)))
    task = fn.rsplit('__', 2)[0]
    rw = d['score'].get('reward')
    r = d.get('rollout') or {}
    out = r.get('output') or {}
    steps = out.get('steps') or []
    npip = 0
    test_success = 0
    for s in steps:
        if s.get('source') != 'agent':
            continue
        obs = str(s.get('observation') or '')
        for c in (s.get('tool_calls') or []):
            args = c.get('arguments') or c.get('input') or {}
            cmd = args.get('command') if isinstance(args, dict) else None
            if not cmd:
                continue
            if 'pip install' in cmd or 'pip3 install' in cmd or cmd.startswith('pip'):
                npip += 1
    print(f"{task:45s} {rw!s:5s} {npip}")
