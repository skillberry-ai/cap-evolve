import json, os, glob, re

TRAJ = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004/trajectories"

FAILING = [
    "django__django-10554", "django__django-12325", "django__django-14376",
    "django__django-15629", "django__django-16667",
    "matplotlib__matplotlib-22871", "pydata__xarray-6461", "pydata__xarray-6992",
    "pylint-dev__pylint-4661", "pylint-dev__pylint-4970",
    "pytest-dev__pytest-10356", "pytest-dev__pytest-5787",
    "sphinx-doc__sphinx-9258", "sympy__sympy-15599", "sympy__sympy-17139",
    "sympy__sympy-17630", "sympy__sympy-18211", "sympy__sympy-21612",
]

PAT = re.compile(r"python|pytest|py\.test|runtests|bin/test|tox|conda|pip install|verify-fix", re.I)

for f in sorted(glob.glob(os.path.join(TRAJ, "*.json"))):
    data = json.load(open(f))
    tid = data["score"]["task_id"]
    if tid not in FAILING:
        continue
    steps = (data["rollout"].get("output") or {}).get("steps", [])
    print("#" * 110)
    print(f"## {tid}  reward={data['score']['reward']}")
    print("#" * 110)
    for s in steps:
        obs = s.get("observation") or {}
        cmd = ""
        for tc in (s.get("tool_calls") or []):
            cmd += (tc.get("arguments", {}) or {}).get("command", "") + "\n"
        cmd = cmd.strip()
        if not cmd:
            continue
        obs_txt = ""
        try:
            for r in (obs.get("results") or []):
                c = r.get("content", "")
                try:
                    j = json.loads(c)
                    obs_txt = f"rc={j.get('returncode')} | " + (j.get("output") or "")[:400]
                except Exception:
                    obs_txt = c[:400]
        except Exception:
            pass
        if PAT.search(cmd):
            print(f"--- step {s.get('step_id')}")
            print("CMD:", cmd[:600].replace("\n", " ⏎ "))
            print("OBS:", obs_txt.replace("\n", " | ")[:500])
            print()
