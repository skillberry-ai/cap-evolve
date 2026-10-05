import json

d = json.load(open('trajectories/django__django-16667__cand_0002__t0.json'))
steps = (d['rollout'].get('trace') or {}).get('steps') or []
for i, s in enumerate(steps[:4]):
    print(f"=== step {i} source={s.get('source')}")
    for k in s:
        if k in ('tool_calls', 'observation'):
            continue
        v = s[k]
        sv = v if isinstance(v, str) else json.dumps(v)
        print(f"  [{k}] {sv[:1500]}")
    print()
