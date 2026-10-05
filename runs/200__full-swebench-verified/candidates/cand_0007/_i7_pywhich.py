import json, os

TRAJ = "trajectories"
# Check whether `python`/`python3` on PATH has the repo importable:
# 1. Do PASSING tasks ever run `python -c "import <pkg>"` successfully from the repo?
# 2. Do FAILING tasks hit ModuleNotFoundError when running `python`?
# Key question: is `python` == /opt/miniconda3/envs/testbed/bin/python (which has the
# repo installed), while PATH python lacks deps?  Look for evidence in the traces:
# commands that printed python version / path.

for t in ["django__django-16667", "django__django-11555", "django__django-13401",
          "django__django-13569", "django__django-15863", "django__django-16032"]:
    p = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
    d = json.load(open(p))
    steps = d["rollout"]["output"]["steps"]
    print("#" * 80)
    print("##", t)
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        obs = ""
        rc = None
        if s.get("observation"):
            try:
                c = s["observation"]["results"][0]["content"]
                j = json.loads(c)
                obs = j.get("output", "") or ""
                rc = j.get("returncode")
            except Exception:
                pass
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            if any(m in cmd for m in ("which python", "python --version", "python -V",
                                      "python3 --version", "sys.executable", "sys.path",
                                      "pip show", "python -c", "python3 -c")):
                print(f"  @{idx} rc={rc} :: {cmd[:160]}")
                print(f"      out: {obs[:300]}")
