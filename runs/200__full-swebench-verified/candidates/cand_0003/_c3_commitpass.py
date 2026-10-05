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

# passing tasks
PASSING = ["django__django-12039","django__django-12276","django__django-13121","django__django-13401",
"django__django-13410","django__django-13569","django__django-14580","django__django-15103","django__django-15380",
"django__django-15851","django__django-15863","django__django-15930","matplotlib__matplotlib-22871",
"matplotlib__matplotlib-24637","scikit-learn__scikit-learn-25232","sphinx-doc__sphinx-7910","sphinx-doc__sphinx-8035",
"sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595","sphinx-doc__sphinx-9258","sympy__sympy-12096","sympy__sympy-13480",
"sympy__sympy-17139","sympy__sympy-18211"]

n_committed = 0
for task in PASSING:
    d = load(task)
    steps = d['rollout']['trace']['steps']
    agent_cmds = []
    for s in steps:
        if s.get('source') == 'agent':
            for tc in (s.get('tool_calls') or []):
                agent_cmds.append(((tc.get('arguments') or {}).get('command','')))
    committed = any(c.startswith('git commit') or ' git commit ' in c for c in agent_cmds)
    n_committed += int(committed)
    last = agent_cmds[-1] if agent_cmds else ''
    print(f"{task:45s} committed={committed!s:5s} ncmd={len(agent_cmds):3d} last={last[:50]!r}")
print(f"\n{n_committed}/{len(PASSING)} passing tasks committed")
