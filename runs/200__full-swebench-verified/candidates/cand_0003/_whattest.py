import json, os, sys

TRAJ = "trajectories"

# For every task: find evidence about how the verifier runs tests and what
# the default `python` is, plus whether `python -m pytest` or `runtests.py`
# ever worked, and which commands actually verified the fix.
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

for f in sorted(os.listdir(TRAJ)):
    d = json.load(open(os.path.join(TRAJ, f)))
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    task = f.split("__")[0]
    worked = []
    for s in steps:
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            if rc == 0 and ("passed" in (obs or "").lower() or " ok" in (obs or "").lower() or "OK" in (obs or "")):
                if any(k in cmd for k in ("pytest", "runtests", "test", "unittest")) and "grep" not in cmd.split()[0] if cmd.split() else False:
                    worked.append(cmd.replace("\n", " ")[:120])
    if worked:
        print(f"### {task}")
        for w in worked[:4]:
            print("   ", w)
