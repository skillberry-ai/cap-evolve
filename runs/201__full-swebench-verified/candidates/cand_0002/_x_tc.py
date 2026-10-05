import json, sys
d = json.load(open(sys.argv[1]))
r = d['rollout']
print('tool_calls:')
for tc in r['tool_calls']:
    print(json.dumps(tc)[:800])
print()
print('metadata:', json.dumps(r.get('metadata'))[:500])
# notes
print('notes:', r['output'].get('notes'))
