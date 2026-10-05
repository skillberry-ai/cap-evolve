import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# For astropy 13453: what did the agent actually change in html.py?
# The error is 'HTMLData' object has no attribute 'cols' — the agent called
# self.data._set_col_formats() but HTMLData doesn't have cols. The GOLD patch likely
# formats differently. Look at the agent's final commit diff.
d = load("astropy__astropy-13453")
out = ((d.get("rollout") or {}).get("output")) or {}
steps = out.get("steps") or []
for i, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    for tc in (s.get("tool_calls") or []):
        c = (tc.get("arguments") or {}).get("command", "")
        if "python -" in c and "html.py" in c:
            print("=" * 80)
            print("STEP", i)
            print(c[:3000])
            if s.get("observation"):
                try:
                    j = json.loads(s["observation"]["results"][0]["content"])
                    print("--- OBS (rc=%s) ---" % j.get("returncode"))
                    print((j.get("output") or "")[:800])
                except Exception as e:
                    print("obs parse fail", e)
