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

# For each failing task: how did the agent's own verification attempts fail (env) vs real logic?
# Focus: did the agent ever get a GREEN verification of the gold test suite? And what runner exists?
for task in sys.argv[1:]:
    d = load(task)
    steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
    print("=" * 90)
    print("###", task)
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        c = cmd_of(s)
        obs, rc = obs_of(s)
        if any(m in c for m in ("pytest", "runtests", "bin/test", "python -m unittest", "python -m pytest", "./tests", "runtests.py")):
            print(f"[{i}] rc={rc} :: {c[:180]}")
            for l in (obs or "").splitlines()[-6:]:
                print("     |", l[:150])
