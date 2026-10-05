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
    ro = d['rollout']
    vs = (ro.get('metadata') or {}).get('verifier_stdout') or ''
    steps = ro['trace']['steps']
    agent_cmds = []
    for s in steps:
        if s.get('source') == 'agent':
            for tc in (s.get('tool_calls') or []):
                agent_cmds.append(((tc.get('arguments') or {}).get('command','')))
    # Did agent COMMIT? (git commit)
    committed = any(c.startswith('git commit') or ' git commit ' in c for c in agent_cmds)
    # Last command
    last = agent_cmds[-1] if agent_cmds else ''
    # Extract test-run verdict from verifier stdout
    print(f"### {task}: steps={len(steps)} committed={committed} last_cmd={last[:60]!r}")
