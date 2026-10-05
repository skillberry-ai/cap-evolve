import json, os, sys

TRAJ = "trajectories"

def obs_of(s):
    obs, rc = "", None
    if s.get("observation"):
        try:
            c = s["observation"]["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output", "")
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc

FAILING = [
    "django__django-10554","django__django-11555","django__django-12325","django__django-13121",
    "django__django-13401","django__django-14007","django__django-14376","django__django-15629",
    "django__django-15930","django__django-16032","django__django-16667","matplotlib__matplotlib-22871",
    "pydata__xarray-6992","pylint-dev__pylint-4661","pylint-dev__pylint-4970","pytest-dev__pytest-10356",
    "pytest-dev__pytest-5787","sphinx-doc__sphinx-9258","sympy__sympy-15599","sympy__sympy-17139",
    "sympy__sympy-17630","sympy__sympy-18211","sympy__sympy-21612",
]
PASSING = [
    "astropy__astropy-13453","django__django-12039","django__django-12276","django__django-12708",
    "django__django-13410","django__django-13569","django__django-13809","django__django-14580",
    "django__django-15103","django__django-15380","django__django-15851","django__django-15863",
    "django__django-16485","matplotlib__matplotlib-24637","pydata__xarray-6461",
    "scikit-learn__scikit-learn-25232","sphinx-doc__sphinx-7910","sphinx-doc__sphinx-8035",
    "sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595","sphinx-doc__sphinx-9367","sympy__sympy-12096",
    "sympy__sympy-13480","sympy__sympy-24213",
]

def analyze(task):
    p = os.path.join(TRAJ, f"{task}__seed__t0.json")
    d = json.load(open(p))
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    out = dict(task=task, n=0, apply128=0, fallback_edits=0, pip=0, repro_fail=0, tail_diff=0,
               pytest127=0, commit=0, stub=0, minimal_explore=0, n_cmds=0)
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        out["n"] += 1
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            out["n_cmds"] += 1
            if "git apply" in cmd:
                if isinstance(rc, int) and rc != 0:
                    out["apply128"] += 1
            if "pip install" in cmd:
                out["pip"] += 1
            if cmd.startswith("python - <<") or cmd.startswith("python3 - <<") or cmd.startswith("python - << 'PY'"):
                if "Path(" in cmd and (".replace(" in cmd or ".write" in cmd):
                    out["fallback_edits"] += 1
            if "git add" in cmd and "git commit" in cmd:
                out["commit"] += 1
            if "mkdir -p mpmath" in cmd or "mpmath" in cmd and "cat >" in cmd:
                out["stub"] += 1
            if "pytest" in cmd and rc == 127:
                out["pytest127"] += 1
            if rc not in (0, None) and ("ModuleNotFoundError" in (obs or "") or "ImportError" in (obs or "")):
                out["repro_fail"] += 1
    # tail diff loop: last 6 agent commands
    tailcmds = []
    for s in steps:
        if s.get("source") == "agent":
            for tc in (s.get("tool_calls") or []):
                tailcmds.append((tc.get("arguments") or {}).get("command", ""))
    for c in tailcmds[-6:]:
        if "git diff" in c or "git --no-pager diff" in c or "git --no-pager show" in c:
            out["tail_diff"] += 1
    return out

print(f"{'task':40s} {'cmds':>4s} {'apply128':>8s} {'fbedit':>6s} {'pip':>3s} {'pytest127':>9s} {'importfail':>10s} {'commit':>6s} {'taildiff':>8s}")
for t in FAILING:
    o = analyze(t)
    print(f"{t:40s} {o['n_cmds']:4d} {o['apply128']:8d} {o['fallback_edits']:6d} {o['pip']:3d} {o['pytest127']:9d} {o['repro_fail']:10d} {o['commit']:6d} {o['tail_diff']:8d}")
print()
for t in PASSING:
    o = analyze(t)
    print(f"{t:40s} {o['n_cmds']:4d} {o['apply128']:8d} {o['fallback_edits']:6d} {o['pip']:3d} {o['pytest127']:9d} {o['repro_fail']:10d} {o['commit']:6d} {o['tail_diff']:8d}")
