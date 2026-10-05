import json, os, sys, re

TRAJ = 'trajectories'
FAILING = ["astropy__astropy-13453","django__django-10554","django__django-11555",
    "django__django-12325","django__django-12708","django__django-14007",
    "django__django-14376","django__django-15629","django__django-16032",
    "django__django-16667","pydata__xarray-6461","pydata__xarray-6992",
    "pylint-dev__pylint-4661","pylint-dev__pylint-4970","pytest-dev__pytest-10356",
    "pytest-dev__pytest-5787","sympy__sympy-15599","sympy__sympy-17630",
    "sympy__sympy-21612","sympy__sympy-24213"]

# For failing tasks: count git-apply attempts and how many failed (rc=128 'unrecognized input')
# plus what the agent did instead.
tot_apply_fail = 0
tasks_with_apply_fail = []
for t in FAILING:
    fn = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    d = json.load(open(fn))
    out = (d.get('rollout') or {}).get('output') or {}
    steps = out.get('steps') or []
    nfail = 0
    for s in steps:
        if s.get('source') != 'agent':
            continue
        obs = s.get('observation') or {}
        try:
            j = json.loads(obs['results'][0]['content'])
            rc = j.get('returncode')
            o = j.get('output', '') or ''
        except Exception:
            rc, o = None, ''
        for tc in (s.get('tool_calls') or []):
            cmd = (tc.get('arguments') or {}).get('command', '')
            if 'git apply' in cmd and 'git apply --check' not in cmd:
                if isinstance(rc, int) and rc != 0:
                    nfail += 1
    if nfail:
        tasks_with_apply_fail.append((t, nfail))
        tot_apply_fail += nfail

print("total failed git-apply attempts across failing tasks:", tot_apply_fail)
for t, n in tasks_with_apply_fail:
    print(f"  {t}: {n}")
