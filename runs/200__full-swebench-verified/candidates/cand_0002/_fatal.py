import json, sys, os

TRAJ = 'trajectories'

FATAL = 'FATAL ERROR - NO MORE STEPS'

for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith('.json'):
        continue
    d = json.load(open(os.path.join(TRAJ, fn)))
    out = ((d.get('rollout') or {}).get('output')) or {}
    steps = out.get('steps') or []
    reward = (d.get('score') or {}).get('reward')
    # Look for the fatal error message and for obs containing truncation notice
    fatal = False
    truncated_steps = 0
    empty_resp = 0
    submit_ok = False
    last_cmd = ''
    for s in steps:
        obs = s.get('observation') or {}
        for r in (obs.get('results') or []):
            c = r.get('content', '')
            if FATAL in c:
                fatal = True
            if 'No tool calls found' in c:
                empty_resp += 1
        tcs = s.get('tool_calls') or []
        for tc in tcs:
            c = (tc.get('arguments') or {}).get('command', '')
            if 'COMPLETE_TASK' in c:
                submit_ok = True
            last_cmd = c
    task = fn.replace('__seed__t0.json', '')
    print(f"{task:45s} r={reward} steps={len(steps):3d} fatal={fatal} empty_resp={empty_resp} submit={submit_ok}")
    if fatal or (len(steps) >= 40):
        print(f"    last_cmd: {last_cmd[:160]}")
