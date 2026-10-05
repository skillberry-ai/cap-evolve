import json, sys

fn = sys.argv[1]
d = json.load(open(fn))
steps = d['rollout']['output']['steps']
start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
end = int(sys.argv[3]) if len(sys.argv) > 3 else len(steps)
for s in steps[start:end]:
    src = s.get('source', '?')
    msg = s.get('message', '')
    if isinstance(msg, dict):
        msg = json.dumps(msg)
    print('=' * 20, 'step', s.get('step_id'), 'source', src, '=' * 20)
    print(str(msg)[:3000])
    print()
