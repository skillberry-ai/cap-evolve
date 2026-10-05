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

def steps_of(d):
    r = d["rollout"]
    return (r.get("trace") or {}).get("steps") or []

def dump_task(task, maxn=100):
    d = load(task)
    if d is None:
        print("NO TRAJ", task)
        return
    steps = steps_of(d)
    print(f"##### {task} reward={d['score']['reward']} nsteps={len(steps)}")
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            if not c:
                continue
            print(f"--- [{i}] rc={rc}: {c[:400]}")
            if obs and rc not in (0,):
                print("    OUT(err):", (obs[-700:] if len(obs) > 700 else obs).replace("\n", " | ")[:700])

import sys
for t in sys.argv[1:]:
    dump_task(t)
