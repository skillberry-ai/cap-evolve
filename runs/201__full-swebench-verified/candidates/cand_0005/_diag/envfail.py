"""Mine all failing-task traces for env/runner failure signals."""
import glob
import json
import re

FAIL = {
    "django__django-10554", "django__django-12325", "django__django-14376",
    "django__django-15629", "django__django-16667", "matplotlib__matplotlib-22871",
    "pydata__xarray-6461", "pydata__xarray-6992", "pylint-dev__pylint-4661",
    "pylint-dev__pylint-4970", "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sphinx-doc__sphinx-9258", "sympy__sympy-15599", "sympy__sympy-17139",
    "sympy__sympy-17630", "sympy__sympy-18211", "sympy__sympy-21612",
}
PASS = {
    "astropy__astropy-13453", "django__django-11555", "django__django-12039",
    "django__django-12276", "django__django-12708", "django__django-13121",
    "django__django-13401", "django__django-13410", "django__django-13569",
    "django__django-13809", "django__django-14007", "django__django-14580",
    "django__django-15103", "django__django-15380", "django__django-15851",
    "django__django-15863", "django__django-15930", "django__django-16032",
    "django__django-16485", "matplotlib__matplotlib-24637",
    "scikit-learn__scikit-learn-25232", "sphinx-doc__sphinx-7910",
    "sphinx-doc__sphinx-8035", "sphinx-doc__sphinx-8475", "sphinx-doc__sphinx-8595",
    "sphinx-doc__sphinx-9367", "sympy__sympy-12096", "sympy__sympy-13480",
    "sympy__sympy-24213",
}

SIGNALS = [
    ("ModuleNotFoundError", re.compile(r"ModuleNotFoundError: No module named '([^']+)'")),
    ("command not found", re.compile(r"(\S+): command not found")),
    ("conda-env run", re.compile(r"(/opt/\S+/envs/\S+/bin/\S+)")),
    ("which python", re.compile(r"which python")),
]


def cmds(path):
    d = json.load(open(path))
    steps = d["rollout"]["trace"]["steps"]
    out = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in s.get("tool_calls") or []:
            cmd = (tc.get("arguments") or {}).get("command", "")
            out.append(cmd)
        obs = ""
        for r in (s.get("observation") or {}).get("results") or []:
            c = r.get("content", "")
            try:
                j = json.loads(c)
                obs = (j.get("output") or "")[:4000]
            except Exception:
                obs = c[:2000]
    return d, out


for f in sorted(glob.glob("trajectories/*.json")):
    d = json.load(open(f))
    tid = d["rollout"]["task_id"]
    if tid not in FAIL:
        continue
    steps = d["rollout"]["trace"]["steps"]
    mods, nf, envs = [], [], set()
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in s.get("tool_calls") or []:
            cmd = (tc.get("arguments") or {}).get("command", "")
            for m in re.findall(r"python\S* ", cmd):
                pass
        for r in (s.get("observation") or {}).get("results") or []:
            c = r.get("content", "")
            try:
                j = json.loads(c)
                outp = (j.get("output") or "")
            except Exception:
                outp = ""
            for m in re.findall(r"ModuleNotFoundError: No module named '([^']+)'", outp):
                mods.append(m)
            for m in re.findall(r"(\S+): command not found", outp):
                nf.append(m)
            for m in re.findall(r"/opt/conda/envs/(\S+?)/bin", outp):
                envs.add(m)
    print(f"== {tid}: mods={sorted(set(mods))} notfound={sorted(set(nf))} envs={sorted(envs)}")
