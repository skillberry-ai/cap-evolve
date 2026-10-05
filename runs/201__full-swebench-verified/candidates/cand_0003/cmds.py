import json, os

TRAJ = 'trajectories'
# For each task, print all commands (in order, compact) to spot environment interactions
task = os.sys.argv[1]
d = json.load(open(f'{TRAJ}/{task}__seed__t0.json'))
r = d['rollout']
trace = r.get('trace') or r.get('output')
for s in trace['steps']:
    tcs = s.get('tool_calls') or []
    obs = s.get('observation') or {}
    for tc in tcs:
        args = tc.get('arguments', {})
        cmd = args.get('command', '') if isinstance(args, dict) else ''
        print(f"[{s.get('step_id')}] CMD: {cmd[:220]}")
