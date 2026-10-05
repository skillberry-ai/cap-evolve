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

def steps_of(task):
    d = load(task)
    out = (d.get("rollout") or {}).get("output") or {}
    return out.get("steps") or []

# astropy: check step 34 (the actual edit heredoc) and 35 (commit) and 36 (repro)
for idx in (32, 34, 35, 36, 37):
    steps = steps_of("astropy__astropy-13453")
    s = steps[idx]
    for tc in (s.get("tool_calls") or []):
        cmd = (tc.get("arguments") or {}).get("command", "")
        obs, rc = obs_of(s)
        print(f"===== [{idx}] rc={rc} =====")
        print(cmd[:1800])
        print("--- OBS (first 800) ---")
        print((obs or "")[:800])
        print()
