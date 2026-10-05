import json, os, sys

TRAJ = 'trajectories'
TASKS = sys.argv[1:]
for t in TASKS:
    fn = os.path.join(TRAJ, t + '__cand_0002__t0.json')
    if not os.path.exists(fn):
        print(f"## {t}: MISSING")
        continue
    d = json.load(open(fn))
    print(f"########## {t} (reward={d['score'].get('reward')})")
    out = d['rollout']['output']
    for s in out['steps']:
        if s.get('source') != 'agent':
            continue
        for c in (s.get('tool_calls') or []):
            args = c.get('arguments') or c.get('input') or {}
            cmd = args.get('command') if isinstance(args, dict) else None
            if cmd:
                print(f"  [{s.get('step_id')}] {cmd[:240]}")
    md = d['rollout'].get('metadata') or {}
    vs = md.get('verifier_stdout', '') or ''
    # last lines of verifier
    print("  --- verifier tail ---")
    print('\n'.join('    ' + l for l in vs.splitlines()[-25:]))
