import json, os, sys

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

# For each task: which import-check approach did the agent use, and what failed?
# Specifically capture the ModuleNotFoundError / import failure signatures.
for f in sorted(os.listdir(TRAJ)):
    d = json.load(open(os.path.join(TRAJ, f)))
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    task = f.split("__")[0]
    fails = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        if rc in (0, None):
            continue
        o = obs or ""
        if "ModuleNotFoundError" in o or "ImportError" in o:
            # extract module name
            for ln in o.splitlines():
                if "ModuleNotFoundError" in ln or "ImportError" in ln:
                    fails.append(ln.strip()[:110])
                    break
    if fails:
        print(f"### {task}")
        for x in fails[:3]:
            print("   ", x)
