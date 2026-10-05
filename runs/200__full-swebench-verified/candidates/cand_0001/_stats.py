import json, os, sys

TRAJ = "trajectories"

def final_message(task):
    data = json.load(open(os.path.join(TRAJ, f"{task}__seed__t0.json")))
    out = data["rollout"]["output"]
    steps = out.get("steps") or []
    # find last assistant message
    msgs = []
    for s in steps:
        if s.get("source") == "agent" and s.get("message"):
            msgs.append(s["message"])
    if not msgs:
        return "(no agent message)"
    return msgs[-1]

def n_cmd_attempts(task):
    """Count distinct issue of git apply failing"""
    data = json.load(open(os.path.join(TRAJ, f"{task}__seed__t0.json")))
    steps = (data["rollout"].get("trace") or {}).get("steps") or []
    n_apply_fail = 0
    n_pytest_missing = 0
    n_import_error = 0
    n_edits = 0
    for s in steps:
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = "", None
            if s.get("observation"):
                try:
                    c = s["observation"]["results"][0]["content"]
                    j = json.loads(c)
                    obs = j.get("output", "")
                    rc = j.get("returncode")
                except Exception:
                    pass
            if cmd.startswith("git apply") and isinstance(rc, int) and rc != 0:
                n_apply_fail += 1
            if "pytest" in cmd and isinstance(rc, int) and rc == 127:
                n_pytest_missing += 1
            if "ModuleNotFoundError" in obs or "ImportError" in obs:
                n_import_error += 1
            if cmd.startswith("python") and "- <<" in cmd or cmd.startswith("python -"):
                n_edits += 1
    return n_apply_fail, n_pytest_missing, n_import_error

if __name__ == "__main__":
    for t in sys.argv[1:]:
        af, pm, ie = n_cmd_attempts(t)
        print(f"{t}: git_apply_fail={af} pytest_missing={pm} import_errors={ie}")
