import json, os, glob

TRAJ = "trajectories"

# Look for successful real-test verification in ALL tasks (passing and failing).
# A "real test verification" = a command that ran the repo's actual test for the
# target issue and produced pass/fail output (not 127/not-found, not masked).

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

MARKERS = ("pytest", "runtests.py", "-m unittest", "tox")

for p in sorted(glob.glob(os.path.join(TRAJ, "*.json"))):
    base = os.path.basename(p)
    task = base.split("__")[0] + "__" + base.split("__")[1]
    d = json.load(open(p))
    steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
    if not steps:
        continue
    events = []
    for idx, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            obs, rc = obs_of(s)
            for m in MARKERS:
                if m in cmd:
                    head = cmd.split("\n")[0][:90]
                    events.append((idx, rc, head))
    print(f"{task:44s} ", " || ".join(f"[{i}]{r}:{h[20:70]}" for i, r, h in events[:8]))
