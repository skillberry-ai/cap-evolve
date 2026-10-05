import json
d = json.load(open("trajectories/sympy__sympy-21612__seed__t0.json"))
steps = d["rollout"]["trace"]["steps"]
for s in steps:
    sid = s.get("step_id")
    if sid in ("19","20","27","30"):
        print(f"\n===== step {sid} keys: {list(s.keys())}")
        for tc in (s.get("tool_calls") or []):
            obs = tc.get("observation")
            print("tool_call keys:", list(tc.keys()))
            print("observation type:", type(obs).__name__)
            print("observation value:", str(obs)[:900])
