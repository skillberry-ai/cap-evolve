import json, os
d = json.load(open('trajectories/django__django-12039__cand_0002__t0.json'))
out = ((d.get('rollout') or {}).get('output')) or {}
steps = out.get('steps') or []
u = [s['message'] for s in steps if s.get('source') == 'user'][0]
j = u.find('## Useful command examples')
print(u[j:j+4500])
