import json, os, glob

TRAJ = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004/trajectories"

# look for env markers in observations: which python is used, references to conda envs
for f in sorted(glob.glob(os.path.join(TRAJ, "*.json"))):
    data = json.load(open(f))
    tid = data["score"]["task_id"]
    steps = (data["rollout"].get("output") or {}).get("steps", [])
    pyenv = set()
    for s in steps:
        obs = s.get("observation") or {}
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
        try:
            for r in (obs.get("results") or []):
                c = r.get("content", "")
                try:
                    j = json.loads(c)
                    out = j.get("output") or ""
                except Exception:
                    out = c
                for line in out.splitlines():
                    if "miniconda" in line or "envs/testbed" in line or "/opt/" in line:
                        pyenv.add(line.strip()[:150])
        except Exception:
            pass
    if pyenv:
        print(f"== {tid} reward={data['score']['reward']}")
        for l in sorted(pyenv)[:12]:
            print("   ", l)
