import json, os, sys

TRAJ = 'trajectories'
fn = sys.argv[1]
msglen = int(sys.argv[2]) if len(sys.argv) > 2 else 700
obslen = int(sys.argv[3]) if len(sys.argv) > 3 else 1500
d = json.load(open(os.path.join(TRAJ, fn)))
out = d['rollout']['output']
steps = out['steps']

def cut(s, n):
    if s is None:
        return ''
    s = str(s)
    if len(s) > n:
        return s[:n // 2] + f"\n  ...[{len(s)} total]...\n" + s[-n // 2:]
    return s

for s in steps:
    src = s.get('source')
    if src in ('system', 'user'):
        continue
    tc = s.get('tool_calls') or []
    print(f"===== step {s.get('step_id')} =====")
    if s.get('message'):
        print("THINK:", cut(s.get('message'), msglen))
    for c in tc:
        if isinstance(c, dict):
            fn_ = c.get('function') or {}
            name = fn_.get('name') or c.get('name')
            args = fn_.get('arguments') or c.get('arguments') or c.get('input')
            print(f"  CALL {name}: {cut(json.dumps(args), obslen)}")
        else:
            print("  CALL(raw):", cut(json.dumps(c), obslen))
    if s.get('observation'):
        print("OBS:", cut(s.get('observation'), obslen))
    print()
