import json
d = json.load(open('trajectories/sympy__sympy-21612__seed__t0.json'))
trace = d['rollout']['trace']
for s in trace['steps']:
    tcs = s.get('tool_calls') or []
    obs = s.get('observation') or {}
    obs_str = json.dumps(obs)
    for tc in tcs:
        cmd = tc.get('arguments', {}).get('command', '')
        if 'pip' in cmd or 'bin/test' in cmd or cmd.startswith('python -'):
            print('STEP', s.get('step_id'), 'CMD:', cmd[:150].replace('\n', ' | '))
            print('  OBS:', obs_str[:400].replace('\\n', ' | '))
