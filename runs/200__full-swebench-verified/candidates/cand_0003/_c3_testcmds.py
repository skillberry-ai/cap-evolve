import json, os, sys

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

def obs_of(step):
    obs = step.get('observation')
    if not obs: return '', None
    try:
        c = obs['results'][0]['content']
        j = json.loads(c)
        return j.get('output', ''), j.get('returncode')
    except Exception:
        return '', None

FAILING = ["astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
"django__django-12708","django__django-14007","django__django-14376","django__django-15629","django__django-16032",
"django__django-16667","pydata__xarray-6461","pydata__xarray-6992","pylint-dev__pylint-4661","pylint-dev__pylint-4970",
"pytest-dev__pytest-10356","pytest-dev__pytest-5787","sympy__sympy-15599","sympy__sympy-17630","sympy__sympy-21612","sympy__sympy-24213"]

for task in FAILING:
    d = load(task)
    steps = d['rollout']['trace']['steps']
    agent_steps = [s for s in steps if s.get('source') == 'agent']
    # Look for verification runs: how many test commands were run, and how many had rc==0 vs rc!=0
    test_cmds = []
    for s in agent_steps:
        out, rc = obs_of(s)
        for tc in (s.get('tool_calls') or []):
            cmd = (tc.get('arguments') or {}).get('command','')
            if any(m in cmd for m in ('pytest', 'runtests.py', 'bin/test', 'python -m pytest', './tests/runtests')):
                test_cmds.append((cmd, rc))
    print(f"### {task}: test cmds run = {len(test_cmds)}")
    for cmd, rc in test_cmds:
        print(f"    rc={rc!s:5s} {cmd[:120]}")
