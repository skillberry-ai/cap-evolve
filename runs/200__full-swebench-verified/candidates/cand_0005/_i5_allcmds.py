import json, os, sys

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

def obs_of(s):
    if not s.get("observation"):
        return "", None
    try:
        j = json.loads(s["observation"]["results"][0]["content"])
        return j.get("output", "") or "", j.get("returncode")
    except Exception:
        return "", None

def cmd_of(s):
    for tc in (s.get("tool_calls") or []):
        return (tc.get("arguments") or {}).get("command", "")
    return ""

task = sys.argv[1]
d = load(task)
steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
for i, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    c = cmd_of(s)
    obs, rc = obs_of(s)
    # print ALL commands with rc and first line of output
    print(f"[{i}] rc={rc} :: {c[:200]}")
    if rc not in (0, None):
        for l in (obs or "").splitlines()[-8:]:
            print("     |", l[:160])
