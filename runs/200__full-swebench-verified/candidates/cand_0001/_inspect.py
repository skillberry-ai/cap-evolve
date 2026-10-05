import json, os, glob

TRAJ = "trajectories"
# Deeper: which commands failed in a passing task (django-13809 has 11 rcfail but passed)?
t = "django__django-13809"
with open(os.path.join(TRAJ, f"{t}__seed__t0.json")) as fh:
    data = json.load(fh)
steps = (data["rollout"].get("trace") or {}).get("steps") or []
for s in steps:
    if s.get("source") != "agent":
        continue
    for tc in (s.get("tool_calls") or []):
        cmd = (tc.get("arguments") or {}).get("command", "")
        obs = ""
        rc = ""
        if s.get("observation"):
            try:
                c = s["observation"]["results"][0]["content"]
                j = json.loads(c)
                obs = j.get("output", "")
                rc = j.get("returncode", "")
            except Exception:
                pass
        mark = "X" if isinstance(rc, int) and rc != 0 else " "
        print(f"[{s['step_id']:>3}]{mark} rc={rc!s:>4} | {cmd[:160]}")
        if mark == "X":
            print(f"        OUT: {obs[:250]}")
