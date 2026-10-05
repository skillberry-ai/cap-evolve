import json, os, re, sys
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

def steps_of(task):
    d = load(task)
    out = (d.get("rollout") or {}).get("output") or {}
    return out.get("steps") or []

task = sys.argv[1]
i_want = int(sys.argv[2]) if len(sys.argv) > 2 else None
steps = steps_of(task)
for i, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    tcs = s.get("tool_calls") or []
    for tc in tcs:
        cmd = (tc.get("arguments") or {}).get("command", "")
        obs, rc = obs_of(s)
        # Only show full command+obs for chosen steps
        if i_want is not None and i != i_want:
            continue
        print(f"===== [{i}] rc={rc} =====")
        print(cmd)
        print("--- OBS ---")
        print((obs or "")[:2500])
