import json, os

TRAJ = "trajectories"
# How do PASSING tasks verify? What commands do they use to run tests?  Maybe they use
# the special "testbed" conda env python. Let's look at a couple of passing traces'
# full command list to see what env they used for testing.
for t in ["django__django-13401", "django__django-15930", "sphinx-doc__sphinx-7910", "sympy__sympy-17139"]:
    d = json.load(open(os.path.join(TRAJ, f"{t}__cand_0002__t0.json")))
    steps = d["rollout"]["output"]["steps"]

    def obs_of(s):
        obs, rc = "", None
        if s.get("observation"):
            try:
                c = s["observation"]["results"][0]["content"]
                j = json.loads(c)
                obs = j.get("output", "") or j.get("output_head", "") or ""
                rc = j.get("returncode")
            except Exception:
                pass
        return obs, rc

    print("#" * 90)
    print("##", t)
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            if any(m in cmd for m in ("pytest", "runtests", "unittest", "tox", "python -m", "python3 -m")):
                print(f"  @{idx} rc={rc} :: {cmd[:180].replace(chr(10), ' ')}")
                if rc not in (0, None):
                    print(f"        out: {obs[:200].replace(chr(10), ' | ')}")
