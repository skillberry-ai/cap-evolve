import json, os, glob

TRAJ = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004/trajectories"

PASSING = ["astropy__astropy-13453", "django__django-12039", "django__django-13410",
           "scikit-learn__scikit-learn-25232", "sympy__sympy-24213", "sphinx-doc__sphinx-8475",
           "django__django-14007", "sympy__sympy-12096", "sphinx-doc__sphinx-9367"]

for f in sorted(glob.glob(os.path.join(TRAJ, "*.json"))):
    data = json.load(open(f))
    tid = data["score"]["task_id"]
    if tid not in PASSING:
        continue
    steps = (data["rollout"].get("output") or {}).get("steps", [])
    print("#" * 100)
    print("##", tid, "reward", data["score"]["reward"])
    for s in steps:
        cmd = ""
        for tc in (s.get("tool_calls") or []):
            cmd += (tc.get("arguments") or {}).get("command", "") + "\n"
        obs = s.get("observation") or {}
        obs_txt = ""
        try:
            for r in (obs.get("results") or []):
                c = r.get("content", "")
                try:
                    j = json.loads(c)
                    obs_txt = f"rc={j.get('returncode')} | " + (j.get("output") or "")[:500]
                except Exception:
                    obs_txt = c[:500]
        except Exception:
            pass
        c = cmd.strip()
        if c and ("verify-fix" in c or "git commit" in c or "git add" in c or "runtests" in c or "pytest" in c or "bin/test" in c or "git diff" in c or "git stash" in c):
            print(f"--- step {s.get('step_id')}")
            print("CMD:", c[:400].replace("\n", " ⏎ "))
            print("OBS:", obs_txt.replace("\n", " | ")[:400])
            print()
