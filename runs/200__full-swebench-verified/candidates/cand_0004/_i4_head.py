import json, os, sys

TRAJ = 'trajectories'

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + '__'):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667",
]
PASSING = [
    "django__django-12039","django__django-12276","django__django-13121","django__django-13401",
    "django__django-13410","django__django-13569","django__django-14580","django__django-15103",
    "django__django-15380","django__django-15851","django__django-15863","django__django-15930",
    "matplotlib__matplotlib-22871","matplotlib__matplotlib-24637","scikit-learn__scikit-learn-25232",
    "sphinx-doc__sphinx-7910","sphinx-doc__sphinx-8035","sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595",
    "sphinx-doc__sphinx-9258","sympy__sympy-12096","sympy__sympy-13480","sympy__sympy-17139","sympy__sympy-18211",
]
INFRA = ["django__django-13809","django__django-15280","django__django-15741","django__django-16485","sphinx-doc__sphinx-8638","sphinx-doc__sphinx-9367"]

for task in FAILING[:3]:
    d = load(task)
    steps = (d.get('rollout') or {}).get('trace', {}).get('steps') or []
    print("=" * 100)
    print("TASK", task, "n_steps", len(steps))
    for i, s in enumerate(steps[:8]):
        src = s.get('source')
        msg = s.get('message') or ''
        print(f"--- step {i} [{src}] ---")
        print(msg[:600])
        tc = s.get('tool_calls') or []
        for t in tc:
            print("TOOLCALL:", json.dumps(t)[:500])
