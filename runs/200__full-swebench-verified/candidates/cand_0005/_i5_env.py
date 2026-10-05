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

# Which python is on PATH in the container, per repo? Look for 'which python' outputs or python version markers
# Also check: does 'python' or 'python3' have the repo's deps? The verifier uses /opt/miniconda3/envs/testbed.
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
        if any(m in c for m in ("which python", "python --version", "python -V", "conda env", "envs/testbed", "sys.executable", "python3 --version")):
            print(f"[{i}] rc={rc} :: {c[:180]}")
            for l in (obs or "").splitlines()[:8]:
                print("     |", l[:150])
    # also first user message for env hints
    steps0 = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
    for s in steps0[:4]:
        if s.get("source") == "user":
            msg = s.get("message") or ""
            if len(msg) > 300:
                print("USER MSG (first 500):", msg[:500])
