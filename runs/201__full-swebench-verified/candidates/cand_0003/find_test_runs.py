import json, os, re

TRAJ = 'trajectories'
d = json.load(open(f'{TRAJ}/pylint-dev__pylint-4970__seed__t0.json'))
trace = d['rollout']['trace']
for s in trace['steps']:
    msg = s.get('message', '') or ''
    obs = s.get('observation') or {}
    obs_str = json.dumps(obs)
    if 'rootdir' in obs_str or 'FAILURES' in obs_str or 'pytest' in obs_str[:2000]:
        tcs = s.get('tool_calls') or []
        for tc in tcs:
            cmd = tc.get('arguments', {}).get('command', '')
            print('STEP', s.get('step_id'), 'CMD:', cmd[:200])
        print('OBS:', obs_str[:800])
        print('=====')
