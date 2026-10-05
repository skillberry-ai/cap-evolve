import json, sys

p = sys.argv[1]
with open(p) as f:
    d = json.load(f)
steps = d["rollout"]["output"]["steps"]
for s in steps:
    src = s.get("source", "?")
    if src == "agent":
        tcs = s.get("tool_calls", []) or []
        for tc in tcs:
            cmd = tc.get("arguments", {}).get("command", "")
            print(f"### step {s.get('step_id')} CMD:")
            print(cmd[:2500])
        obs = s.get("observation", {}) or {}
        res = obs.get("results", [])
        for r in res:
            content = r.get("content", "")
            try:
                cj = json.loads(content)
            except Exception:
                cj = {"output": content}
            rc_ = cj.get("returncode", r.get("returncode", 0))
            out = cj.get("output", "") or cj.get("output_head", "")
            exc = cj.get("exception_info", "")
            print(f"--- RC={rc_} {exc}")
            tail = out[-1200:] if len(out) > 1200 else out
            print("--- OUT:")
            print(tail)
        if not tcs:
            print(f"### step {s.get('step_id')} (no tool call)")
            print(s.get("message", "")[:2000])
    elif src == "user":
        print("### USER/TASK:")
        print(s.get("message", "")[:1500])
