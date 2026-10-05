import json, sys, os, re

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

def summarize(task, tag="cand_0002"):
    fn = os.path.join(TRAJ, f"{task}__{tag}__t0.json")
    d = json.load(open(fn))
    steps = d["rollout"]["trace"]["steps"]
    agent_steps = [s for s in steps if s.get("source") == "agent"]
    print(f"\n{'#'*100}\n### {task} — {len(agent_steps)} agent steps")
    for i, s in enumerate(agent_steps):
        tcs = s.get("tool_calls") or []
        msg = (s.get("message") or "").replace("\n", " ")[:150]
        cmds = []
        for tc in tcs:
            cmd = (tc.get("arguments") or {}).get("command", "")
            cmds.append(cmd.replace("\n", " ⏎ ")[:220])
        obs, rc = obs_of(s)
        obs1 = (obs or "").replace("\n", " | ")[:150]
        print(f"[{i:2d}] rc={rc} MSG: {msg}")
        for c in cmds:
            print(f"      CMD: {c}")
        if cmds:
            print(f"      OBS: {obs1}")

for t in sys.argv[1:]:
    summarize(t)
