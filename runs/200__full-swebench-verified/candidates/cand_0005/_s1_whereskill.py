import json
fn = 'trajectories/django__django-10554__cand_0002__t0.json'
d = json.load(open(fn))
out = ((d.get('rollout') or {}).get('output')) or {}
extra = ((out.get('agent') or {}).get('extra')) or {}
cfg = extra.get('agent_config') or {}
print("KEYS:", list(cfg.keys()))
# The user message step 2 includes the task; check whether SKILL.md text appears anywhere
steps = out.get('steps') or []
sysmsg = steps[0]['message']
usermsg = steps[1]['message']
sk = open('SKILL.md').read()
print('SKILL.md len:', len(sk))
print('SKILL text in user msg?', sk[:80] in usermsg)
# find where skill text might be: search a distinctive phrase
phrase = 'NEVER rename test functions'
print('phrase in user msg?', phrase in usermsg)
print('---- user msg first 3000 chars ----')
print(usermsg[:3000])
