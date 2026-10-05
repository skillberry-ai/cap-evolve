import json, os, sys

TR = "trajectories"
name = sys.argv[1] + "__seed__t0.json"
step_ids = [int(x) for x in sys.argv[2:]]
d = json.load(open(os.path.join(TR, name)))
steps = d["rollout"]["output"]["steps"]
for s in steps:
    if s.get("step_id") in step_ids:
        for i, tc in enumerate(s.get("tool_calls") or []):
            cmd = (tc.get("arguments") or {}).get("command", "")
            print(f"=== step {s.get('step_id')} FULL CMD:")
            print(cmd)
        obs = s.get("observation") or {}
        for r in (obs.get("results") or []):
            print("--- FULL OBSERVATION:")
            print(r.get("content", ""))
