import json
d = json.load(open('trajectories/django__django-10554__seed__t0.json'))
steps = d['rollout']['trace']['steps']
msg = steps[1]['message']
i = msg.find('You are an expert software engineer')
print(msg[i+3500:])
