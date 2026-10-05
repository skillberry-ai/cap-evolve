import json, os, sys

TRAJ = 'trajectories'
# For passing tasks: after pytest NOTFOUND, what did they do? Show the follow-up command sequence
# around the pytest attempt.
TASKS = sys.argv[1:]
for t in TASKS:
    fn = os.path.join(TRAJ, t + '__cand_0002__t0.json')
    d = json.load(open(fn))
    print(f"########## {t}")
    out = d['rollout']['output']
    steps = out['steps']
    cmds = []
    for s in steps:
        if s.get('source') != 'agent':
            continue
        for c in (s.get('tool_calls') or []):
            args = c.get('arguments') or c.get('input') or {}
            cmd = args.get('command') if isinstance(args, dict) else None
            if cmd:
                cmds.append((s.get('step_id'), cmd, str(s.get('observation') or '')))
    # print commands after the first pytest NOTFOUND
    seen_first = False
    for sid, cmd, obs in cmds:
        if 'pytest' in cmd.split()[0] if cmd.split() else False:
            seen_first = True
        if seen_first:
            o = obs.replace('\n', ' ')[:150]
            print(f"  [{sid}] {cmd[:170]}")
            print(f"        OBS: {o}")
