import json

d = json.load(open('trajectories/django__django-16667__cand_0002__t0.json'))
steps = (d['rollout'].get('trace') or {}).get('steps') or []
for s in steps:
    if s.get('source') == 'user':
        m = s.get('message', '')
        skill_txt = open('SKILL.md').read()
        prompt_txt = open('prompt.md').read()
        i1 = m.find(skill_txt[:80])
        i2 = m.find(prompt_txt[:80])
        print(f"user msg len={len(m)}; SKILL at {i1}; prompt at {i2}")
        # print region between the issue text and the workflow text
        # find where "You are an expert software engineer" starts
        j = m.find('You are an expert software engineer')
        print("--- user message from workflow start (first 500 chars) ---")
        print(m[j:j+300])
        print("--- tail of user message (last 600 chars) ---")
        print(m[-600:])
        break
