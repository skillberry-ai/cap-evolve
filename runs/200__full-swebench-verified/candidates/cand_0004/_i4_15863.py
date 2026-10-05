import json, os, re
TRAJ = "trajectories"
def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None
def obs_of(s):
    obs, rc = "", None
    if s.get("observation"):
        try:
            c = s["observation"]["results"][0]["content"]
            j = json.loads(c)
            obs = j.get("output", "") or ""
            rc = j.get("returncode")
        except Exception:
            pass
    return obs, rc
def steps_of(task):
    d = load(task)
    out = (d.get("rollout") or {}).get("output") or {}
    return out.get("steps") or []
# 15863 is PASSING. Prior iteration studied it: "how did it get tests running after pip install asgiref?"
steps = steps_of("django__django-15863")
for i, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    for tc in (s.get("tool_calls") or []):
        cmd = (tc.get("arguments") or {}).get("command", "")
        obs, rc = obs_of(s)
        if "pip" in cmd or "pytest" in cmd or cmd.startswith("python"):
            print(f"[{i}] rc={rc}: {cmd[:130]}")
            print("   >", (obs or "")[:300].replace("\n", " | "))
