import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

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
task = sys.argv[1]
start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
end = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9
d = load(task)
steps = (d["rollout"].get("trace") or {}).get("steps") or []
n = 0
for i, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    n += 1
    if n < start or n > end:
        continue
    msg = s.get("message") or ""
    for tc in (s.get("tool_calls") or []):
        c = (tc.get("arguments") or {}).get("command", "")
        obs, rc = obs_of(s)
        print(f"----- [{n}] rc={rc} cmd -----")
        print(c[:1500])
        print(f"----- [{n}] obs (first 1200) -----")
        print((obs or "")[:1200])
    print()
