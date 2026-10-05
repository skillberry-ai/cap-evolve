import json, os, sys, re

TRAJ = 'trajectories'
# What does the verifier's "Updated N paths from <sha>" line tell us? It's the harness
# resetting test files. Look for which files the harness resets per task, and whether
# the agent's own test-file edits clash.
ALL = sorted(f for f in os.listdir(TRAJ) if f.endswith('.json'))
for fn in ALL:
    d = json.load(open(os.path.join(TRAJ, fn)))
    task = fn.rsplit('__', 2)[0]
    rw = d['score'].get('reward')
    r = d.get('rollout') or {}
    md = r.get('metadata') or {}
    vs = md.get('verifier_stdout', '') or ''
    m = re.findall(r'\+ git checkout (\S+) (.*)\n\+ for path in (.*)', vs)
    reset = re.findall(r'git checkout \S+ (\S+)', vs)
    # find "Updated N paths"
    upd = re.findall(r'Updated (\d+) paths? from (\S+)', vs)
    # did agent edit test files?
    r2 = d.get('rollout') or {}
    out = r2.get('output') or {}
    steps = out.get('steps') or []
    test_edits = []
    for s in steps:
        if s.get('source') != 'agent':
            continue
        for c in (s.get('tool_calls') or []):
            args = c.get('arguments') or c.get('input') or {}
            cmd = args.get('command') if isinstance(args, dict) else None
            if not cmd:
                continue
            if re.search(r"Path\(['\"](tests/|testing/)", cmd) or re.search(r"sed -i .*(tests/|testing/)", cmd):
                test_edits.append(cmd[:100])
    if reset or test_edits:
        print(f"== {task} (r={rw}) reset={reset[:3]} updated={upd[:2]}")
        for te in test_edits[:3]:
            print(f"    AGENT_TEST_EDIT: {te}")
