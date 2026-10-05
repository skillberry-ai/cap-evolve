import json
d = json.load(open('trajectories/django__django-10554__seed__t0.json'))
print("ERROR:", json.dumps(d['rollout'].get('error'))[:500])
print("METADATA:", json.dumps(d['rollout'].get('metadata'))[:1500])
print("SCORE:", json.dumps(d['score'])[:800])
