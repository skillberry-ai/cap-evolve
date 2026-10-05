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

# What interpreter/path things run with. Look at first few commands + which python works.
for task in ["django__django-12039", "astropy__astropy-13453", "sympy__sympy-15599", "django__django-16032"]:
    d = load(task)
    steps = d["rollout"]["output"]["steps"]
    print("#" * 100)
    print("##", task)
    n = 0
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            if not c:
                continue
            obs, rc = obs_of(s)
            n += 1
            if n <= 6:
                print(f"[{n}] rc={rc} CMD: {c[:200]}")
                print(f"    OBS: {(obs or '')[:300].splitlines()[:4]}")
    # also find any successful `python -c` runs to see which interpreter works
    print("  -- commands mentioning python path/env --")
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            if re.search(r"(/opt/miniconda|/usr/bin/python|which python|conda|sys\.executable|pip install)", c):
                obs, rc = obs_of(s)
                print(f"  rc={rc} CMD: {c[:250]}")
                for line in (obs or "").splitlines()[:6]:
                    print("      |", line[:200])
