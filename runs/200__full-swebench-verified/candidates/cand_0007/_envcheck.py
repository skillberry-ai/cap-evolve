import json, os, sys

TRAJ = "trajectories"

ALL = sorted(os.listdir(TRAJ))

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

stat = dict(git_apply_ok=0, git_apply_fail=0, envs_seen=0, testbed_bin=0,
            runtests_ok=0, pytest_module_ok=0, first_ls=[], conda_info=[])
for f in ALL:
    d = json.load(open(os.path.join(TRAJ, f)))
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            if "git apply" in cmd:
                if isinstance(rc, int) and rc == 0:
                    stat["git_apply_ok"] += 1
                elif isinstance(rc, int):
                    stat["git_apply_fail"] += 1
            if "/opt/miniconda3/envs" in (obs or "") or "/opt/miniconda3/envs" in cmd:
                stat["envs_seen"] += 1
                if len(stat["conda_info"]) < 3:
                    stat["conda_info"].append((f, cmd[:80], (obs or "")[:200]))
            if "envs/testbed/bin" in cmd:
                stat["testbed_bin"] += 1
            if "runtests.py" in cmd and isinstance(rc, int) and rc == 0:
                stat["runtests_ok"] += 1
                if len(stat["conda_info"]) < 6:
                    stat["conda_info"].append((f, cmd[:100], "RC0"))
            if "-m pytest" in cmd and isinstance(rc, int) and rc == 0:
                stat["pytest_module_ok"] += 1
        # capture the first ls -la observation per file
        if cmd.startswith("ls -la") and not stat["first_ls"] and (obs or "").strip():
            stat["first_ls"].append((f, (obs or "")[:800]))

print(json.dumps({k: v for k, v in stat.items() if k not in ("first_ls", "conda_info")}, indent=1))
print("=== conda/envs evidence ===")
for c in stat["conda_info"]:
    print(c)
print("=== first ls -la (1 sample) ===")
if stat["first_ls"]:
    print(stat["first_ls"][0][0])
    print(stat["first_ls"][0][1])
