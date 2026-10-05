import json, re, os

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
        "sphinx-doc__sphinx-9258","sympy__sympy-12096","sympy__sympy-13480","sympy__sympy-17139","sympy__sympy-18211"]

def load(task):
    return json.load(open(f'trajectories/{task}__cand_0002__t0.json'))

def obs_of(s):
    try:
        c = s['observation']['results'][0]['content']
        j = json.loads(c)
        return j.get('output', ''), j.get('returncode')
    except Exception:
        return '', None

def analyze(task):
    d = load(task)
    steps = (d['rollout'].get('trace') or {}).get('steps') or []
    pytest_nf = 0        # bare pytest not found
    modpytest = 0        # python -m pytest runs
    modpytest_fail = 0
    modpytest_ok = 0
    runtests = 0
    runtests_fail = 0
    for s in steps:
        if s.get('source') != 'agent':
            continue
        for tc in (s.get('tool_calls') or []):
            cmd = (tc.get('arguments') or {}).get('command', '')
            obs, rc = obs_of(s)
            if re.match(r'\s*pytest\b', cmd) and rc == 127:
                pytest_nf += 1
            if 'python -m pytest' in cmd or 'python3 -m pytest' in cmd:
                modpytest += 1
                if isinstance(rc, int) and rc != 0:
                    modpytest_fail += 1
                elif rc == 0:
                    modpytest_ok += 1
            if 'runtests.py' in cmd:
                runtests += 1
                if isinstance(rc, int) and rc != 0:
                    runtests_fail += 1
    return dict(pytest_nf=pytest_nf, modpytest=modpytest, modpytest_fail=modpytest_fail,
                modpytest_ok=modpytest_ok, runtests=runtests, runtests_fail=runtests_fail)

print(f"{'task':40s} {'pytest_nf':>9s} {'-m_pytest':>9s} {'mp_fail':>7s} {'mp_ok':>5s} {'runtests':>8s} {'rt_fail':>7s}")
for t in FAIL + PASS:
    a = analyze(t)
    print(f"{t:40s} {a['pytest_nf']:9d} {a['modpytest']:9d} {a['modpytest_fail']:7d} {a['modpytest_ok']:5d} {a['runtests']:8d} {a['runtests_fail']:7d}")
