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

def analyze(task):
    d = load(task)
    steps = (d.get('rollout') or {}).get('trace', {}).get('steps') or []
    info = dict(task=task, n_cmds=0, pytest_127=0, modulenotfound=0, commit=0,
                backup_files=0, gitapply_128=0, tests_ran_ok=None, n_test_runs=0)
    cmds = []
    for i, s in enumerate(steps):
        if s.get('source') != 'agent':
            continue
        for tc in (s.get('tool_calls') or []):
            c = (tc.get('arguments') or {}).get('command', '')
            obs, rc = obs_of(s)
            info['n_cmds'] += 1
            cmds.append((i, c, obs, rc))
            if 'pytest' in c.split() or c.startswith('pytest'):
                if rc == 127:
                    info['pytest_127'] += 1
                else:
                    info['n_test_runs'] += 1
                    if 'ModuleNotFoundError' in (obs or ''):
                        info['modulenotfound'] += 1
            if 'git apply' in c and rc not in (0, None):
                info['gitapply_128'] += 1
            if 'git commit' in c:
                info['commit'] += 1
            if '.bak' in c and ('cp ' in c or 'mv ' in c):
                info['backup_files'] += 1
    return info

print(f"{'task':44s} {'cmds':>4s} {'py127':>5s} {'MNF':>4s} {'commit':>6s} {'apply!':>6s} {'bak':>3s} {'testok':>6s}")
for t in FAILING + PASSING:
    i = analyze(t)
    print(f"{i['task']:44s} {i['n_cmds']:4d} {i['pytest_127']:5d} {i['modulenotfound']:4d} {i['commit']:6d} {i['gitapply_128']:6d} {i['backup_files']:3d} {i['n_test_runs']:6d}")
