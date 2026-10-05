import json, os

TRAJ = 'trajectories'

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + '__'):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

def obs_of(s):
    if not s.get("observation"):
        return "", None
    try:
        c = s["observation"]["results"][0]["content"]
        j = json.loads(c)
        return j.get("output", "") or "", j.get("returncode")
    except Exception:
        return "", None

# How do PASSING tasks run tests? Extract every test command + rc for a few passing tasks.
PASSING = ["django__django-12039","django__django-13401","django__django-15380","django__django-15863",
           "sphinx-doc__sphinx-9258","sympy__sympy-13480","matplotlib__matplotlib-22871",
           "scikit-learn__scikit-learn-25232","sphinx-doc__sphinx-8595","sympy__sympy-18211"]
for task in PASSING:
    d = load(task)
    steps = (d.get('rollout') or {}).get('trace', {}).get('steps') or []
    print("=" * 90)
    print("TASK", task)
    for i, s in enumerate(steps):
        if s.get('source') != 'agent':
            continue
        for tc in (s.get('tool_calls') or []):
            c = (tc.get('arguments') or {}).get('command', '')
            obs, rc = obs_of(s)
            if any(m in c for m in ('pytest', 'py.test', 'runtests', 'unittest', 'python -m pytest')):
                print(f"  step{i} rc={rc}: {c[:150]}")
                tl = (obs or '')
                for l in tl.splitlines()[-4:]:
                    print("     |", l[:150])
