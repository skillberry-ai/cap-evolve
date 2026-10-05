import json, sys, glob, os

# Render ALL failing trajectories compactly: commands only + first/last obs lines.
fail = ["django__django-10554","django__django-12325","django__django-14376",
        "django__django-15629","django__django-16667","matplotlib__matplotlib-22871",
        "pydata__xarray-6461","pydata__xarray-6992","pylint-dev__pylint-4661",
        "pylint-dev__pylint-4970"]
for t in fail:
    p = f"trajectories/{t}__seed__t0.json"
    d = json.load(open(p))
    r = d['rollout']
    steps = r['output']['steps']
    meta = r.get('metadata') or {}
    print(f"\n############### {t} reward={meta.get('harbor_reward')} steps={len(steps)}")
    for s in steps:
        if s.get('source') != 'agent':
            continue
        for tc in (s.get('tool_calls') or []):
            cmd = (tc.get('arguments') or {}).get('command', '')
            print(f"[{s['step_id']:>3}] CMD: {cmd[:220].replace(chr(10), ' ~ ')}")
