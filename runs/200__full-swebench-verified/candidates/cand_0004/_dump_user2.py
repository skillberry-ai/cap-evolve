import json, sys

fn = sys.argv[1]
d = json.load(open(fn))
steps = d['rollout']['output']['steps']
msg = steps[1]['message']
print(msg[6000:11480])
