import json, os, sys

TRAJ = 'trajectories'
# All failing-with-steps tasks
FAILING = ["astropy__astropy-13453","django__django-10554","django__django-11555",
    "django__django-12325","django__django-12708","django__django-14007",
    "django__django-14376","django__django-15629","django__django-16032",
    "django__django-16667","pydata__xarray-6461","pydata__xarray-6992",
    "pylint-dev__pylint-4661","pylint-dev__pylint-4970","pytest-dev__pytest-10356",
    "pytest-dev__pytest-5787","sympy__sympy-15599","sympy__sympy-17630",
    "sympy__sympy-21612","sympy__sympy-24213"]

def obs_of(s):
    obs = s.get('observation') or {}
    try:
        c = obs['results'][0]['content']
        j = json.loads(c)
        return j.get('output', ''), j.get('returncode')
    except Exception:
        return '', None

stats = {}
for t in FAILING:
    fn = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    d = json.load(open(fn))
    out = (d.get('rollout') or {}).get('output') or {}
    steps = out.get('steps') or []
    n_test_cmds = 0
    test_notfound = 0
    last_test_idx = None
    last_edit_idx = None
    final_msg = ''
    edit_methods = set()
    git_apply_fail = 0
    for idx, s in enumerate(steps):
        if s.get('source') != 'agent':
            continue
        for tc in (s.get('tool_calls') or []):
            cmd = (tc.get('arguments') or {}).get('command', '')
            obs, rc = obs_of(s)
            if cmd:
                if cmd.startswith('git apply') or cmd.startswith('git diff') or cmd.startswith('git add'):
                    pass
                if 'git apply' in cmd and isinstance(rc, int) and rc != 0:
                    git_apply_fail += 1
                if any(m in cmd for m in ('pytest', 'py.test', 'runtests.py', '/bin/test', 'bin/test', 'unittest')):
                    n_test_cmds += 1
                    if isinstance(rc, int) and rc == 127:
                        test_notfound += 1
                    last_test_idx = idx
                if cmd.startswith('python -') or 'sed -i' in cmd or 'Path(' in cmd or cmd.startswith('git apply'):
                    last_edit_idx = idx
        final_msg = s.get('message') or final_msg
    st = dict(n_steps=len(steps), n_test=n_test_cmds, test_127=test_notfound,
              last_test=last_test_idx, last_edit=last_edit_idx, apply_fail=git_apply_fail)
    stats[t] = st
    print(f"{t:44s} steps={st['n_steps']:3d} testcmds={st['n_test']:2d} test127={st['test_127']:2d} lasttest={str(st['last_test']):>4s} lastedit={str(st['last_edit']):>4s} applyfail={st['apply_fail']}")
