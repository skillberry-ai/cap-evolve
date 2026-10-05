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

t = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
r = d["rollout"]
md = r.get("metadata") or {}
rj = md.get("reward_json") or {}
print("REWARD_JSON:", json.dumps(rj, indent=1)[:2000])
# how many paths updated?
vs = md.get("verifier_stdout", "") or ""
import re
upd = re.findall(r"Updated (\d+) paths? from (\w+)", vs)
print("UPDATED PATHS:", upd)
