import json

d = json.load(open('trajectories/django__django-16667__cand_0002__t0.json'))
steps = (d['rollout'].get('trace') or {}).get('steps') or []
# print full user message (the task instance) for 16667
for s in steps:
    if s.get('source') == 'user':
        print(s['message'])
        break
