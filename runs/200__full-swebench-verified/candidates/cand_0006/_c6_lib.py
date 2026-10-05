import json, os, glob

TRAJ = "trajectories"

def obs_of(s):
    ob = s.get("observation")
    if not ob:
        return "", None
    try:
        c = ob["results"][0]["content"]
        j = json.loads(c)
        return (j.get("output") or j.get("output_head") or ""), j.get("returncode")
    except Exception:
        return "", None

def cmd_of(s):
    for tc in (s.get("tool_calls") or []):
        return (tc.get("arguments") or {}).get("command")
    return None

def load(task, tag="cand_0002"):
    fn = os.path.join(TRAJ, f"{task}__{tag}__t0.json")
    return json.load(open(fn))

def dump(task, tag="cand_0002", tail_n=None):
    d = load(task, tag)
    steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
    print(f"\n===================== {task} =====================")
    agen = [(i, s) for i, s in enumerate(steps) if s.get("source") == "agent"]
    if tail_n:
        agen = agen[-tail_n:]
    for i, s in agen:
        cmd = cmd_of(s) or ""
        obs, rc = obs_of(s)
        # compact
        obs_compact = (obs or "").replace("\n", " ⏎ ")[:220]
        print(f"[{i:3d}] rc={rc} $ {cmd[:250]}")
        print(f"      OBS: {obs_compact}")
