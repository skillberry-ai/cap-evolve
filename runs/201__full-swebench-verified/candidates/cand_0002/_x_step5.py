import json, sys

d = json.load(open(sys.argv[1]))
r = d['rollout']
steps = r['output']['steps']
# agent steps alternate message / tool_call; look at raw JSON of one agent step
for s in steps:
    if s['source'] == 'agent' and s['step_id'] == 5:
        print(json.dumps(s, indent=1)[:3000])
        break
# check 'agent' dict
print('AGENT DICT:', json.dumps(r['output']['agent'], indent=1)[:2000])
