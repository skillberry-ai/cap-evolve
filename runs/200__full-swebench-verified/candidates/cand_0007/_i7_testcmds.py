import json, os

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

def show_test_cmds(task):
    p = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(p))
    steps = d["rollout"]["output"]["steps"]
    print("##", task)
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            if any(m in cmd for m in ("pytest", "runtests", "unittest", "tox", "py.test")):
                print(f"  @{idx} rc={rc} :: {cmd[:200].replace(chr(10), ' ')}")
                if rc not in (0, None):
                    print(f"      out: {(obs or '')[-200:].replace(chr(10), ' | ')}")

for t in ["django__django-13121", "django__django-13569", "django__django-11555",
          "django__django-15863", "django__django-15380", "django__django-16667",
          "astropy__astropy-13453", "sympy__sympy-13480", "sphinx-doc__sphinx-8595",
          "matplotlib__matplotlib-22871", "scikit-learn__scikit-learn-25232"]:
    show_test_cmds(t)
    print()
