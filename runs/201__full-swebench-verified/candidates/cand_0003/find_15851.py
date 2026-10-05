import json

d = json.load(open('trajectories/django__django-15851__seed__t0.json'))
trace = d['rollout']['trace']
for s in trace['steps']:
    obs = s.get('observation') or {}
    obs_str = json.dumps(obs)
    if 'client_test' in obs_str:
        print('STEP', s.get('step_id'))
        tcs = s.get('tool_calls') or []
        for tc in tcs:
            print('  CMD:', tc.get('arguments', {}).get('command', '')[:200])
        print('  OBS:', obs_str[:600])
