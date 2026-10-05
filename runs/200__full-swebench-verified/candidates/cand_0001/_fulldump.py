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

def full_dump(task, max_cmd=250, max_obs=400):
    d = json.load(open(os.path.join(TRAJ, f"{task}__seed__t0.json")))
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    print(f"##### {task} reward={d['score']['reward']} steps={len(steps)}")
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            print(f"[{s['step_id']:>3}] rc={rc!s:>4} | {cmd[:max_cmd]}")
            if obs:
                print(f"        OUT: {obs[:max_obs]}".replace(chr(10), ' ⏎ '))
    print()

if __name__ == "__main__":
    for t in sys.argv[1:]:
        full_dump(t)
