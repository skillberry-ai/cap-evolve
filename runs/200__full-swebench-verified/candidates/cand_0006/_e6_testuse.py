import json, os, sys

TRAJ = 'trajectories'
# Cluster commands across ALL failing tasks: what test commands does the agent run?
FAILING = """astropy__astropy-13453 django__django-10554 django__django-11555 django__django-12325
django__django-12708 django__django-14007 django__django-14376 django__django-15629 django__django-16032
django__django-16667 pydata__xarray-6461 pydata__xarray-6992 pylint-dev__pylint-4661 pylint-dev__pylint-4970
pytest-dev__pytest-10356 pytest-dev__pytest-5787 sphinx-doc__sphinx-8638 sphinx-doc__sphinx-9367
sympy__sympy-15599 sympy__sympy-17630 sympy__sympy-21612 sympy__sympy-24213""".split()

for t in FAILING:
    fn = os.path.join(TRAJ, t + '__cand_0002__t0.json')
    if not os.path.exists(fn):
        continue
    d = json.load(open(fn))
    print(f"########## {t}")
    out = d['rollout']['output']
    for s in out['steps']:
        if s.get('source') != 'agent':
            continue
        obs = s.get('observation') or ''
        for c in (s.get('tool_calls') or []):
            args = c.get('arguments') or c.get('input') or {}
            cmd = args.get('command') if isinstance(args, dict) else None
            if not cmd:
                continue
            # Only show test-run-ish commands and their outcomes
            if any(k in cmd for k in ('pytest', 'runtests', 'python -m pytest', 'tox', 'make test', 'python -m unittest')):
                # find outcome
                o = str(obs)
                rc = ''
                if 'not found' in o or '127' in o[:50]:
                    rc = 'NOTFOUND'
                elif 'No module named' in o:
                    rc = 'MODULE_MISSING'
                print(f"  [{s.get('step_id')}] {cmd[:160]}  => {rc}")
