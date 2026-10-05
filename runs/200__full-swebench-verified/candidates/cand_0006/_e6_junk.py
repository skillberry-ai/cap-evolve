import json, os, sys, re

TRAJ = 'trajectories'
# For each failing task, find the LAST git commit and what files the final patch touches,
# and whether junk files (e.g., .bak, stub dirs) got committed.
ALL = sorted(f for f in os.listdir(TRAJ) if f.endswith('.json'))
JUNK = ('.bak', 'mpmath.py', 'mpmath/', '/tmp/', 'newfile', 'repro', 'test_repro', '.py.bak')
for fn in ALL:
    d = json.load(open(os.path.join(TRAJ, fn)))
    task = fn.rsplit('__', 2)[0]
    rw = d['score'].get('reward')
    if (rw or 0) > 0.5:
        continue
    r = d.get('rollout') or {}
    out = r.get('output') or {}
    steps = out.get('steps') or []
    junk_hits = []
    for s in steps:
        if s.get('source') != 'agent':
            continue
        for c in (s.get('tool_calls') or []):
            args = c.get('arguments') or c.get('input') or {}
            cmd = args.get('command') if isinstance(args, dict) else None
            if not cmd:
                continue
            if cmd.startswith('cp ') or (' > ' in cmd and 'mpmath' in cmd) or 'mkdir -p mpmath' in cmd or 'cat > mpmath' in cmd:
                junk_hits.append((s.get('step_id'), cmd[:120]))
            if 'mv ' in cmd[:20]:
                junk_hits.append((s.get('step_id'), cmd[:120]))
    if junk_hits:
        print(f"== {task} (r={rw}):")
        for sid, cmd in junk_hits:
            print(f"   [{sid}] {cmd}")
