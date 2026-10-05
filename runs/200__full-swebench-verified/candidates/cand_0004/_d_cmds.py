import json, os, sys

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

task = sys.argv[1]
d = load(task)
r = d["rollout"]
steps = r["output"]["steps"]
trace = (r.get("trace") or {}).get("steps") or []
print("output steps:", len(steps), "trace steps:", len(trace))
src = trace if trace else steps
for i, s in enumerate(src):
    if s.get("source") != "agent":
        continue
    tcs = s.get("tool_calls") or []
    for tc in tcs:
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
        print(f"--- [{i}] rc={rc} cmd: {cmd[:250]}")
        if obs:
            print("    OUT:", obs[:250].replace("\n", " | "))
