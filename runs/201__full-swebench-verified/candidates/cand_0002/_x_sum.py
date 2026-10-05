import json, glob

files = sorted(glob.glob("trajectories/*.json"))
rows = []
for p in files:
    with open(p) as f:
        d = json.load(f)
    tid = d["score"]["task_id"]
    reward = d["score"]["reward"]
    ro = d["rollout"]
    if ro is None or ro.get("output") is None:
        rows.append((tid, reward, 0, 0, False, False, False, "NO-ROLLOUT"))
        continue
    steps = ro["output"].get("steps") or []
    js = json.dumps(steps)
    cmds = []
    for s in steps:
        for tc in s.get("tool_calls", []) or []:
            a = tc.get("arguments", {})
            cmds.append(a.get("command", ""))
    joined = "\n".join(cmds)
    n_commit = joined.count("git commit")
    has_pytest_missing = ("pytest: not found" in js) or ("No module named 'pytest'" in js)
    has_moderr = "ModuleNotFoundError" in js
    has_complete = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" in joined
    last_cmd = cmds[-1] if cmds else ""
    rows.append((tid, reward, len(steps), n_commit, has_pytest_missing, has_moderr, has_complete, last_cmd[:60]))

print(f"{'task':40s} {'rew':>4s} {'stp':>4s} {'cmt':>4s} {'pyno':>5s} {'moderr':>7s} {'done':>5s} last_cmd")
for r in rows:
    print(f"{r[0]:40s} {r[1]:4.2f} {r[2]:4d} {r[3]:4d} {str(r[4]):>5s} {str(r[5]):>7s} {str(r[6]):>5s} {r[7]}")
