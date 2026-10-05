import json, os

TR = "trajectories"
rows = []
for name in sorted(os.listdir(TR)):
    if not name.endswith(".json"):
        continue
    d = json.load(open(os.path.join(TR, name)))
    sc = d["score"]
    roll = d["rollout"]
    out = roll.get("output") or {}
    steps = out.get("steps") or []
    n_cmds = 0
    submitted = False
    err = roll.get("error")
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in s.get("tool_calls") or []:
            n_cmds += 1
            cmd = (tc.get("arguments") or {}).get("command", "")
            if "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" in cmd:
                submitted = True
    rows.append((sc.get("reward", -1), sc["task_id"], len(steps), n_cmds, submitted, err))

rows.sort()
for r in rows:
    print(f"reward={r[0]:.2f} {r[1]:42s} steps={r[2]:3d} cmds={r[3]:3d} submitted={r[4]} err={str(r[5])[:60]}")
