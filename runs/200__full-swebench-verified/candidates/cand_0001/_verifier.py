import json
d = json.load(open('trajectories/django__django-10554__seed__t0.json'))
vs = d['rollout']['metadata'].get('verifier_stdout', '')
print("VERIFIER_STDOUT (last 4000):")
print(vs[-4000:])
