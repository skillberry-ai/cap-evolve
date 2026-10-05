import json, sys

path = sys.argv[1]
d = json.load(open(path))
r = d['rollout']
steps = r['output']['steps']
# print full messages for agent steps, but truncate very long ones
for s in steps:
    m = s['message'] or ''
    src = s['source']
    if len(m) > 4000:
        m = m[:2000] + f"\n...[{len(m)} chars total]...\n" + m[-1500:]
    print(f"########## [{s['step_id']:>3} {src}] ##########")
    print(m)
    print()
