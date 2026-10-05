import json, os, sys, re

TRAJ = 'trajectories'
ALL = sorted(f for f in os.listdir(TRAJ) if f.endswith('.json'))
for fn in ALL:
    d = json.load(open(os.path.join(TRAJ, fn)))
    task = fn.rsplit('__', 2)[0]
    rw = d['score'].get('reward')
    r = d.get('rollout') or {}
    out = r.get('output') or {}
    steps = out.get('steps') or []
    hits = []
    for s in steps:
        if s.get('source') != 'agent':
            continue
        obs = str(s.get('observation') or '')
        if re.search(r'\d+ passed|\d+ failed|Ran \d+ tests|== FAILURES ==', obs):
            for c in (s.get('tool_calls') or []):
                args = c.get('arguments') or c.get('input') or {}
                cmd = args.get('command') if isinstance(args, dict) else None
                if cmd:
                    hits.append((s.get('step_id'), cmd[:150]))
    if hits:
        print(f"== {task} (r={rw}):")
        for sid, cmd in hits[:6]:
            print(f"   [{sid}] {cmd}")
