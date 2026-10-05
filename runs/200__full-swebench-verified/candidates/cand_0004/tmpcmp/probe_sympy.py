import json, os, re

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
TRAJ = os.path.join(BASE, "trajectories")

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

def obs_of(s):
    obs, rc = "", None
    o = s.get("observation")
    if o:
        try:
            c = o["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output") or j.get("output_head") or ""
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc

# For sympy 15599: did pip install mpmath work, and did the test pass afterwards?
d = load("sympy__sympy-15599")
steps = d["rollout"]["output"]["steps"]
seen_install = False
for s in steps:
    if s.get("source") != "agent":
        continue
    for tc in (s.get("tool_calls") or []):
        c = (tc.get("arguments") or {}).get("command", "")
        obs, rc = obs_of(s)
        if "pip install" in c:
            print("CMD:", c[:200])
            print("  rc:", rc, "OBS:", (obs or "")[:400])
            print()
        if seen_install and ("python" in c[:8] or "pytest" in c or "bin/test" in c):
            print("AFTER-INSTALL CMD:", c[:250])
            print("  rc:", rc)
            print("  OBS:", (obs or "")[:600])
            print()
    if "pip install" in str(s.get("tool_calls")):
        seen_install = True
