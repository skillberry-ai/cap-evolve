import json, sys

fn = sys.argv[1]
d = json.load(open(fn))
steps = d['rollout']['output']['steps']
print('N steps:', len(steps))
s0 = steps[0]
print('step keys:', list(s0.keys()) if isinstance(s0, dict) else type(s0))
print(json.dumps(s0, indent=1)[:1500])
