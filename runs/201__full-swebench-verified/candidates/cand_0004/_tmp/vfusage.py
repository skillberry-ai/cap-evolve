import json, os, glob

TRAJ = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004/trajectories"

rows = []
for f in sorted(glob.glob(os.path.join(TRAJ, "*.json"))):
    data = json.load(open(f))
    tid = data["score"]["task_id"]
    reward = data["score"]["reward"]
    steps = (data["rollout"].get("output") or {}).get("steps", [])
    n_vf = 0
    committed = False
    ran_tests = 0
    for s in steps:
        cmd = ""
        for tc in (s.get("tool_calls") or []):
            cmd += (tc.get("arguments") or {}).get("command", "") + "\n"
        if "verify-fix" in cmd:
            n_vf += 1
        if "git commit" in cmd or "git add" in cmd:
            committed = True
        if "runtests.py" in cmd or "pytest" in cmd or "bin/test" in cmd or "tox" in cmd:
            ran_tests += 1
    rows.append((tid, reward, n_vf, committed, ran_tests))

print(f"{'task':42s} {'rew':>4s} {'vf':>3s} {'commit':>6s} {'testcmd':>7s}")
for tid, reward, n_vf, committed, ran_tests in rows:
    print(f"{tid:42s} {reward:4.2f} {n_vf:3d} {str(committed):>6s} {ran_tests:7d}")
