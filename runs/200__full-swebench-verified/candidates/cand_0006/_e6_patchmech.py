import json, os, sys

TRAJ = 'trajectories'
# How many trials does each failing task have, and what does the LAST agent message look like?
TASKS = sys.argv[1:]
for t in TASKS:
    fn = os.path.join(TRAJ, t + '__cand_0002__t0.json')
    d = json.load(open(fn))
    out = d['rollout']['output']
    steps = out['steps']
    # count git commit / git diff / final echo
    ncommit = ndiff = napply = npython_edit = 0
    for s in steps:
        if s.get('source') != 'agent':
            continue
        for c in (s.get('tool_calls') or []):
            args = c.get('arguments') or c.get('input') or {}
            cmd = args.get('command') if isinstance(args, dict) else None
            if not cmd:
                continue
            if cmd.startswith('git apply') or 'git apply' in cmd.split('\n')[0]:
                napply += 1
            elif cmd.startswith('git add') or 'git commit' in cmd[:40]:
                ncommit += 1
            elif cmd.startswith('python') and ('Path(' in cmd or 'read_text' in cmd):
                npython_edit += 1
    print(f"{t}: steps={len(steps)} git_apply_attempts={napply} commits={ncommit} python_edit_scripts={npython_edit}")
