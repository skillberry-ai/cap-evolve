import json, os, sys

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

task = sys.argv[1]
d = load(task)
ro = d['rollout']
steps = ro['trace']['steps']
for s in steps:
    src = s.get('source')
    sid = s.get('step_id')
    if src == 'agent':
        # find tool_calls
        tcs = s.get('tool_calls') or []
        for tc in tcs:
            args = tc.get('arguments') or {}
            cmd = args.get('command', '')
            print(f"--- [{sid}] CMD: {cmd[:300]}")
        msg = s.get('message') or ''
        if msg and not tcs:
            print(f"--- [{sid}] MSG: {msg[:200]}")
    elif src in ('system', 'user', 'environment'):
        pass
