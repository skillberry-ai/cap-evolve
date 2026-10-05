import json
fn = 'trajectories/django__django-10554__cand_0002__t0.json'
d = json.load(open(fn))
out = ((d.get('rollout') or {}).get('output')) or {}
steps = out.get('steps') or []
usermsg = steps[1]['message']
print('len user msg:', len(usermsg))
# print from where skill begins
i = usermsg.find('You are an expert software engineer')
print(usermsg[i:i+6000])
