import json, os, sys

TRAJ = "trajectories"

def load(task):
    return json.load(open(os.path.join(TRAJ, f"{task}__seed__t0.json")))

def summary(task):
    data = load(task)
    steps = (data["rollout"].get("trace") or {}).get("steps") or []
    n_agent = sum(1 for s in steps if s.get("source") == "agent")
    # find commands testing behavior: runtests.py / unittest / direct python repro
    test_cmds = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = "", None
            if s.get("observation"):
                try:
                    c = s["observation"]["results"][0]["content"]
                    j = json.loads(c)
                    obs = j.get("output", "")
                    rc = j.get("returncode")
                except Exception:
                    pass
            if ("runtests.py" in cmd or "unittest" in cmd or "pytest" in cmd or "py.test" in cmd):
                test_cmds.append((cmd[:100], rc, obs[:150]))
    print(f"### {task} reward={data['score']['reward']} agent_steps={n_agent} test_cmds={len(test_cmds)}")
    for c, rc, o in test_cmds:
        print(f"   rc={rc} | {c}")
        if rc not in (0, None) and o:
            print(f"      OUT: {o}".replace(chr(10), " | "))
    print()

if __name__ == "__main__":
    for t in sys.argv[1:]:
        summary(t)
