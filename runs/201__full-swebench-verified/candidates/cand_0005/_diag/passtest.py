"""What do PASSING tasks do to run tests? Compare env discovery."""
import glob
import json
import re

PASS = [
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
]

for f in sorted(glob.glob("trajectories/*.json")):
    d = json.load(open(f))
    tid = d["rollout"]["task_id"]
    if tid not in PASS:
        continue
    steps = d["rollout"]["trace"]["steps"]
    test_cmds = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in s.get("tool_calls") or []:
            cmd = (tc.get("arguments") or {}).get("command", "")
            if re.search(r"(pytest|runtests\.py|bin/test|python -m pytest)", cmd):
                obs = ""
                for r in (s.get("observation") or {}).get("results") or []:
                    c = r.get("content", "")
                    try:
                        j = json.loads(c)
                        obs = (j.get("output") or "").strip().replace("\n", " | ")[:150]
                    except Exception:
                        obs = c[:100]
                test_cmds.append((s.get("step_id"), cmd[:130], obs))
    print(f"\n== {tid}")
    for sid, cmd, obs in test_cmds[:8]:
        print(f"   [{sid}] {cmd}")
        print(f"        -> {obs[:140]}")
