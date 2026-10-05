import json, os, sys

FAIL = ["astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
        "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
        "django__django-16032","django__django-16667","pydata__xarray-6992","pylint-dev__pylint-4661",
        "pylint-dev__pylint-4970","pytest-dev__pytest-10356","pytest-dev__pytest-5787",
        "sympy__sympy-15599","sympy__sympy-17630","sympy__sympy-21612"]
PASS = ["django__django-12039","django__django-12276","django__django-13121","django__django-13401",
        "django__django-13410","django__django-13569","django__django-14580","django__django-15103",
        "django__django-15380","django__django-15851","django__django-15863","django__django-15930",
        "matplotlib__matplotlib-22871","matplotlib__matplotlib-24637","scikit-learn__scikit-learn-25232",
        "sphinx-doc__sphinx-7910","sphinx-doc__sphinx-8035","sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595",
        "sympy__sympy-12096","sympy__sympy-13480","sympy__sympy-17139","sympy__sympy-18211","sympy__sympy-24213"]

def load(task):
    return json.load(open(f'trajectories/{task}__cand_0002__t0.json'))

def steps_of(d):
    return (d['rollout'].get('trace') or {}).get('steps') or []

def cmds_of(d):
    out = []
    for s in steps_of(d):
        if s.get('source') != 'agent':
            continue
        for tc in (s.get('tool_calls') or []):
            c = (tc.get('arguments') or {}).get('command', '')
            if c:
                out.append(c)
    return out

import re
print(f"{'task':40s} {'n_cmd':>5s} {'test_runs':>9s} {'gitapply':>8s} {'python_edit':>11s} {'commit':>6s} {'submit':>6s} {'lastdiff':>8s}")
for task in FAIL + PASS[:8]:
    d = load(task)
    cs = cmds_of(d)
    n = len(cs)
    testruns = sum(1 for c in cs if re.search(r'(^|\s|&&|\|)(python .*runtests|pytest|py\.test|python -m pytest)', c))
    gitapply = sum(1 for c in cs if 'git apply' in c)
    pyedit = sum(1 for c in cs if c.startswith('python -') or 'python - <<' in c or 'python <<' in c)
    commit = sum(1 for c in cs if 'git commit' in c)
    submit = sum(1 for c in cs if 'COMPLETE_TASK_AND_SUBMIT' in c)
    lastdiff = sum(1 for c in cs[-6:] if 'git diff' in c or 'git --no-pager diff' in c)
    print(f"{task:40s} {n:5d} {testruns:9d} {gitapply:8d} {pyedit:11d} {commit:6d} {submit:6d} {lastdiff:8d}")
