import json, os, sys, re

TR = "trajectories"

def load(task):
    return json.load(open(os.path.join(TR, task + "__seed__t0.json")))

def iter_cmd_obs(task):
    """Yield (step_id, cmd, parsed_output_text) for every agent tool call."""
    d = load(task)
    for s in d["rollout"]["output"]["steps"]:
        if s.get("source") != "agent":
            continue
        tcs = s.get("tool_calls") or []
        obs = s.get("observation") or {}
        results = obs.get("results") or []
        for i, tc in enumerate(tcs):
            cmd = (tc.get("arguments") or {}).get("command", "")
            content = results[i].get("content", "") if i < len(results) else ""
            try:
                j = json.loads(content)
                out = j.get("output") or j.get("output_head") or ""
                rc = j.get("returncode")
            except Exception:
                out, rc = content, None
            yield s.get("step_id"), cmd, out, rc

task = sys.argv[1]
for sid, cmd, out, rc in iter_cmd_obs(task):
    print(f"--- step {sid} rc={rc} CMD: {cmd[:300]}")
    tail = out[-800:] if len(out) > 800 else out
    print(f"OUT(tail): {tail}")
    print()
