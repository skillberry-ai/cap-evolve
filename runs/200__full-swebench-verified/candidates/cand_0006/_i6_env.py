import json, os

TRAJ = './trajectories'

def get_steps(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    d = json.load(open(fn))
    ro = d.get("rollout") or {}
    return ((ro.get("trace") or {}).get("steps")) or []

# Search all traces for evidence about the environment: conda envs, /opt paths, which python
MARKERS = ["miniconda3/envs", "conda activate", "conda run", "conda env", "which python", "envs/testbed", "testbed/bin"]

for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith(".json"):
        continue
    task = fn.replace("__cand_0002__t0.json", "")
    steps = get_steps(task)
    hits = []
    for i, s in enumerate(steps):
        if s.get("source") != "agent":
            continue
        obs = s.get("observation")
        out = ""
        if obs:
            try:
                j = json.loads(obs.get("results")[0].get("content"))
                out = (j.get("output") or "") + (j.get("output_head") or "")
            except Exception:
                pass
        msg = s.get("message") or ""
        for tc in (s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command") or ""
            for m in MARKERS:
                if m in cmd:
                    hits.append((i, "CMD", m, cmd[:120]))
                if m in out:
                    hits.append((i, "OUT", m, out[:200].replace("\n", " | ")))
    if hits:
        print(f"### {task}")
        for h in hits[:8]:
            print(f"  [{h[0]}] {h[1]} ({h[2]}): {h[3]!r}")
