import json, os, sys

fn = sys.argv[1]
maxlen = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
d = json.load(open(fn))
out = d['rollout']['output']
steps = out['steps']
for s in steps:
    sid = s.get('step_id')
    src = s.get('source')
    msg = s.get('message') or ''
    # Truncate long messages but show head+tail
    if len(msg) > maxlen:
        msg = msg[:maxlen//2] + f"\n...[TRUNC {len(msg)} chars]...\n" + msg[-maxlen//2:]
    print(f"===== step {sid} [{src}] =====")
    print(msg)
    print()
