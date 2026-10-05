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

# per task: list every command that ran tests with rc==0 AND had passing output
for f in sorted(os.listdir(TRAJ)):
    d = json.load(open(os.path.join(TRAJ, f)))
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    task = f.split("__")[0]
    rows = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            first = cmd.split()[0] if cmd.split() else ""
            if first in ("grep", "sed", "nl", "ls", "cat", "find", "git"):
                continue
            if ("runtests" in cmd or "pytest" in cmd or "bin/test" in cmd or "unittest" in cmd
                    or "tox" in cmd or "runpy" in cmd):
                rows.append((rc, cmd.replace("\n", " ")[:150]))
    if rows:
        print(f"### {task}")
        for rc, cmd in rows[:8]:
            print(f"  rc={rc}: {cmd}")
