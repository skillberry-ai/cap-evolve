import json, os, glob

TRAJ = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004/trajectories"

rows = []
for f in sorted(glob.glob(os.path.join(TRAJ, "*.json"))):
    data = json.load(open(f))
    tid = data["score"]["task_id"]
    reward = data["score"]["reward"]
    steps = (data["rollout"].get("output") or {}).get("steps", [])
    err = data["rollout"].get("error")
    # count bash commands
    cmds = []
    for s in steps:
        for tc in (s.get("tool_calls") or []):
            c = tc.get("arguments", {}).get("command", "")
            cmds.append(c)
    rows.append((tid, reward, len(steps), len(cmds), err, cmds))

print(f"{'task':45s} {'reward':>6s} {'steps':>5s} {'cmds':>5s} err")
for tid, reward, ns, nc, err, cmds in rows:
    print(f"{tid:45s} {reward:6.2f} {ns:5d} {nc:5d} {err}")

print()
print("=== FAILING ===")
for tid, reward, ns, nc, err, cmds in rows:
    if reward < 0.5:
        print(f"\n### {tid} reward={reward} steps={ns} cmds={nc}")
