import json, os, sys

TRAJ = 'trajectories'
def obs_of(s):
    obs = s.get('observation') or {}
    try:
        c = obs['results'][0]['content']
        j = json.loads(c)
        return j.get('output', ''), j.get('returncode')
    except Exception:
        return '', None

# For each failing task: check whether pytest/runtests "not found" occurred, and what fallbacks were tried.
FAILING = ["astropy__astropy-13453","django__django-10554","django__django-11555",
    "django__django-12325","django__django-12708","django__django-14007",
    "django__django-14376","django__django-15629","django__django-16032",
    "django__django-16667","pydata__xarray-6461","pydata__xarray-6992",
    "pylint-dev__pylint-4661","pylint-dev__pylint-4970","pytest-dev__pytest-10356",
    "pytest-dev__pytest-5787","sympy__sympy-15599","sympy__sympy-17630",
    "sympy__sympy-21612","sympy__sympy-24213"]

for t in FAILING:
    fn = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    d = json.load(open(fn))
    out = (d.get('rollout') or {}).get('output') or {}
    steps = out.get('steps') or []
    events = []
    for idx, s in enumerate(steps):
        if s.get('source') != 'agent':
            continue
        for tc in (s.get('tool_calls') or []):
            cmd = (tc.get('arguments') or {}).get('command', '')
            obs, rc = obs_of(s)
            o = obs or ''
            if 'No module named' in o and rc not in (0,):
                mod = ''
                for mm in ('numpy','pandas','mpmath','asgiref','pytest','django','appdirs','astroid','attr','toml','antlr'):
                    if f"No module named '{mm}'" in o:
                        mod = mm
                        break
                events.append(f"s{idx}:importfail:{mod or '?'}")
            if rc == 127 and 'not found' in o:
                events.append(f"s{idx}:cmdnotfound")
    print(f"{t:40s} {events[:12]}")
