import json, os, sys

TR = "trajectories"
name = sys.argv[1] + "__seed__t0.json"
d = json.load(open(os.path.join(TR, name)))
steps = d["rollout"]["output"]["steps"]
# find the task step (source=user, contains issue)
issue = ""
for s in steps:
    if s.get("source") == "user":
        issue = s.get("message", "")
        break
print("=== ISSUE (first 2500 chars) ===")
print(issue[:2500])
print()
print("=== AGENT COMMANDS + OBSERVATIONS ===")
for s in steps:
    if s.get("source") != "agent":
        continue
    tcs = s.get("tool_calls") or []
    obs = s.get("observation") or {}
    results = obs.get("results") or []
    for i, tc in enumerate(tcs):
        cmd = (tc.get("arguments") or {}).get("command", "")
        content = ""
        if i < len(results):
            content = results[i].get("content", "")
        # try to parse content as json to get output
        out = content
        try:
            j = json.loads(content)
            out = (j.get("output") or j.get("output_head") or "")[:600]
        except Exception:
            pass
        print(f"--- step {s.get('step_id')} CMD: {cmd[:400]}")
        print(f"    OUT: {out[:600]}")
        print()
