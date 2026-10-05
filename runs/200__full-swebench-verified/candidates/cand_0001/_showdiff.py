import json, os, sys

TRAJ = "trajectories"

def show_diff(task):
    d = json.load(open(os.path.join(TRAJ, f"{task}__seed__t0.json")))
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            if ("git" in cmd and "diff" in cmd) or "git commit" in cmd:
                obs = ""
                if s.get("observation"):
                    try:
                        c = s["observation"]["results"][0]["content"]
                        j = json.loads(c)
                        obs = j.get("output", "")
                    except Exception:
                        pass
                if "diff --git" in obs:
                    print(f"===== {task} =====")
                    print(obs[:3000])
                    print()
                    return

if __name__ == "__main__":
    for t in sys.argv[1:]:
        show_diff(t)
