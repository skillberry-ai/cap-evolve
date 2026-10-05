import json, sys, os

TRAJ = 'trajectories'
fn = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, fn)))
out = ((d.get('rollout') or {}).get('output')) or {}
steps = out.get('steps') or []

# Print a compact command log: step_id, message (truncated), commands
for s in steps:
    src = s.get('source')
    if src != 'agent':
        continue
    msg = (s.get('message') or '').strip()
    tcs = s.get('tool_calls') or []
    obs = s.get('observation') or {}
    results = obs.get('results') or []
    cmds = []
    for tc in tcs:
        args = tc.get('arguments') or {}
        c = args.get('command', '')
        cmds.append(c.replace('\n', ' ⏎ ')[:200])
    outs = []
    for r in results:
        c = r.get('content', '')
        # try parse JSON with returncode/output
        try:
            j = json.loads(c)
            rc = j.get('returncode')
            o = (j.get('output') or '').replace('\n', ' ⏎ ')[:220]
            outs.append(f'rc={rc} out={o}')
        except Exception:
            outs.append(c.replace('\n', ' ⏎ ')[:220])
    print(f"--- step {s.get('step_id')} ---")
    if msg:
        print(f"  MSG: {msg[:300]}")
    for c in cmds:
        print(f"  CMD: {c}")
    for o in outs:
        print(f"  OBS: {o}")
