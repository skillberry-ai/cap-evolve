import json, os, glob

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

rows = []
for p in sorted(glob.glob(os.path.join(TRAJ, "*.json"))):
    base = os.path.basename(p)
    task = base.split("__")[0] + "__" + base.split("__")[1]
    d = json.load(open(p))
    steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
    if not steps:
        continue
    n_pytest127 = 0
    used_runtests = False
    used_unittest = False
    used_pymodule_test = False
    pip_install_pytest = False
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            if cmd.startswith("pytest") or cmd.startswith("python -m pytest"):
                if rc == 127:
                    n_pytest127 += 1
            if "runtests.py" in cmd:
                used_runtests = True
            if "-m unittest" in cmd:
                used_unittest = True
            if cmd.startswith("python -m ") and "test" in cmd:
                used_pymodule_test = True
            if "pip" in cmd and "pytest" in cmd:
                pip_install_pytest = True
    rows.append((task, n_pytest127, used_runtests, used_unittest, used_pymodule_test, pip_install_pytest))

print(f"{'task':42s} {'py127':>5s} {'rt':>3s} {'uni':>3s} {'pym':>3s} {'pip':>3s}")
for r in rows:
    print(f"{r[0]:42s} {r[1]:5d} {str(r[2]):>3s} {str(r[3]):>3s} {str(r[4]):>3s} {str(r[5]):>3s}")
