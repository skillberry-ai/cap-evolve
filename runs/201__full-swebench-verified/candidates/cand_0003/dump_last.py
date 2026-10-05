import json, sys, os

TRAJ = 'trajectories'

task = sys.argv[1]
max_show = int(sys.argv[2]) if len(sys.argv) > 2 else 99999
d = json.load(open(f'{TRAJ}/{task}__seed__t0.json'))
r = d['rollout']
trace = r.get('trace') or r.get('output')
steps = trace['steps']
n = len(steps)
print(f'#### TASK {task}  steps={n}  reward={d.get("score", {}).get("reward")}')
fb = d.get('score', {}).get('feedback', '')
print('FEEDBACK:', fb[:300])
# print last steps in detail
start = max(0, n - max_show)
for s in steps[start:]:
    src = s.get('source', '?')
    tcs = s.get('tool_calls') or []
    obs = s.get('observation') or {}
    msg = s.get('message', '') or ''
    print(f"--- step {s.get('step_id')} [{src}]")
    if msg:
        print('MSG:', str(msg)[:600])
    for tc in tcs:
        args = tc.get('arguments', {})
        cmd = args.get('command', json.dumps(args)) if isinstance(args, dict) else str(args)
        print('CMD:', str(cmd)[:500].replace('\n', ' \\n '))
    if obs:
        res = obs.get('results', [])
        for rr in res:
            content = rr.get('content', '')
            # content is a JSON string with returncode/output
            try:
                cj = json.loads(content)
                out = cj.get('output', '')
                rc = cj.get('returncode')
                print(f'OBS rc={rc}:', str(out)[:400].replace('\n', ' | '))
            except Exception:
                print('OBS:', str(content)[:300])
    print()
