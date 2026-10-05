import json, os, sys

TRAJ = "trajectories"

def load(task):
    with open(os.path.join(TRAJ, f"{task}__seed__t0.json")) as fh:
        return json.load(fh)

def dump(task, max_cmd=200, max_obs=250):
    data = load(task)
    steps = (data["rollout"].get("trace") or {}).get("steps") or []
    print(f"##### {task} reward={data['score']['reward']} steps={len(steps)}")
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = "", ""
            if s.get("observation"):
                try:
                    c = s["observation"]["results"][0]["content"]
                    j = json.loads(c)
                    obs = j.get("output", "")
                    rc = j.get("returncode", "")
                except Exception:
                    pass
            mark = "X" if isinstance(rc, int) and rc not in (0,) else " "
            print(f"[{s['step_id']:>3}]{mark} rc={rc!s:>4} | {cmd[:max_cmd]}")
            if mark == "X" and obs:
                print(f"        OUT: {obs[:max_obs]}".replace(chr(10), " | "))
    print()

if __name__ == "__main__":
    for t in sys.argv[1:]:
        dump(t)
