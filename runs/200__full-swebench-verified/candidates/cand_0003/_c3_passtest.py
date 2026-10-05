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

# What commands do PASSING tasks run for verification? Look at test commands in passing tasks.
PASSING = ["django__django-12039","django__django-12276","django__django-13410","django__django-15380",
"sphinx-doc__sphinx-7910","sympy__sympy-17139","matplotlib__matplotlib-22871","scikit-learn__scikit-learn-25232"]

for task in PASSING:
    d = load(task)
    steps = d['rollout']['trace']['steps']
    agent_steps = [s for s in steps if s.get('source') == 'agent']
    print(f"### {task}")
    for s in agent_steps:
        out, rc = obs_of(s)
        for tc in (s.get('tool_calls') or []):
            cmd = (tc.get('arguments') or {}).get('command','')
            if any(m in cmd for m in ('pytest', 'runtests.py', 'bin/test', 'python -m pytest', 'python -m unittest', 'tox')):
                # exclude reads
                if cmd.startswith(('sed','cat','ls','grep','nl')): continue
                print(f"    rc={rc!s:5s} {cmd[:150]}")
    print()
