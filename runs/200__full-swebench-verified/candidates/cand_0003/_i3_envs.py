import json, re, os

# Understand which python env is used: check for hints in traces about /opt/miniconda3/envs/testbed vs /opt/miniconda3
for task in ["django__django-16667", "django__django-10554", "pylint-dev__pylint-4970", "sympy__sympy-15599", "pytest-dev__pytest-5787", "astropy__astropy-13453"]:
    fn = f'trajectories/{task}__cand_0002__t0.json'
    d = json.load(open(fn))
    steps = (d['rollout'].get('trace') or {}).get('steps') or []
    envs = set()
    for s in steps:
        for tc in (s.get('tool_calls') or []):
            cmd = (tc.get('arguments') or {}).get('command', '')
            for m in re.findall(r'/opt/miniconda3[^ \n:;]*', cmd):
                envs.add(m)
        try:
            c = s['observation']['results'][0]['content']
            j = json.loads(c)
            for m in re.findall(r'/opt/miniconda3[^ \n:;]*', j.get('output', '') or ''):
                envs.add(m)
        except Exception:
            pass
    print(f"### {task}")
    for e in sorted(envs):
        print("   ", e)
