import json, os, re, sys

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

# Track for each task: was there a "git apply" with the LLM-style patch format that failed?
# Pattern: "git apply" + heredoc containing "*** Begin Patch" → rc != 0
tasks = sys.argv[1:]
if not tasks:
    tasks = sorted(f.split("__")[0] + "|" + f for f in os.listdir(TRAJ))
    tasks = [t.split("|")[0] for t in tasks]

for t in tasks:
    d = load(t)
    if d is None:
        continue
    steps = (d["rollout"].get("trace") or {}).get("steps") or []
    n_applypatch_fail = 0
    n_sed_or_py_edit = 0
    reward = (d.get("score") or {}).get("reward")
    for s in steps:
        if s.get("source") != "agent":
            continue
        obs, rc = obs_of(s)
        for tc in (s.get("tool_calls") or []):
            c = (tc.get("arguments") or {}).get("command", "")
            if c.startswith("git apply") and "*** Begin Patch" in c and rc not in (0, None):
                n_applypatch_fail += 1
    print(f"{t:45s} r={reward} applypatch_style_fail={n_applypatch_fail}")
