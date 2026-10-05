import json, os

TRAJ = "trajectories"
# For each failing AND passing task: what fraction of agent steps were spent BEFORE the
# first edit vs. after? And crucially: did the agent ever get a SUCCESSFUL test run?
# A "successful test run" = a command that is a test command with rc==0.

def obs_of(s):
    obs, rc = "", None
    if s.get("observation"):
        try:
            c = s["observation"]["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output", "") or ""
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc

import sys
which = sys.argv[1] if len(sys.argv) > 1 else "failing"
if which == "failing":
    TASKS = ["astropy__astropy-13453", "django__django-10554", "django__django-11555",
             "django__django-12325", "django__django-12708", "django__django-14007",
             "django__django-14376", "django__django-15629", "django__django-16032",
             "django__django-16667"]
else:
    TASKS = ["django__django-12039", "django__django-12276", "django__django-13121"]

TEST_MARKERS = ("pytest", "runtests.py", "unittest", "py.test", "tox -e")

for t in TASKS:
    d = json.load(open(os.path.join(TRAJ, f"{t}__cand_0002__t0.json")))
    steps = d["rollout"]["output"]["steps"]
    runs = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            if any(m in cmd for m in TEST_MARKERS):
                runs.append((cmd[:100].replace("\n", " "), rc))
    print("##", t)
    for c, rc in runs:
        print(f"   rc={rc} {c}")
