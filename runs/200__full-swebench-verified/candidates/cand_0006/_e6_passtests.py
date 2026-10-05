import json, os, sys

TRAJ = 'trajectories'
# What commands does the agent run to TEST on PASSING tasks? This is what a good flow looks like.
PASSING = """django__django-12039 django__django-12276 django__django-13121 django__django-13401 django__django-13410
django__django-13569 django__django-14580 django__django-15103 django__django-15380 django__django-15851
django__django-15863 django__django-15930 matplotlib__matplotlib-22871 matplotlib__matplotlib-24637
scikit-learn__scikit-learn-25232 sphinx-doc__sphinx-7910 sphinx-doc__sphinx-8035 sphinx-doc__sphinx-8475
sphinx-doc__sphinx-8595 sphinx-doc__sphinx-9258 sympy__sympy-12096 sympy__sympy-13480 sympy__sympy-17139 sympy__sympy-18211""".split()

for t in PASSING[:12]:
    fn = os.path.join(TRAJ, t + '__cand_0002__t0.json')
    if not os.path.exists(fn):
        continue
    d = json.load(open(fn))
    print(f"########## {t}")
    out = d['rollout']['output']
    for s in out['steps']:
        if s.get('source') != 'agent':
            continue
        for c in (s.get('tool_calls') or []):
            args = c.get('arguments') or c.get('input') or {}
            cmd = args.get('command') if isinstance(args, dict) else None
            if not cmd:
                continue
            if any(k in cmd for k in ('pytest', 'runtests', 'python -m pytest', 'tox', 'make test', 'unittest', 'python -m test')):
                print(f"  [{s.get('step_id')}] {cmd[:200]}")
