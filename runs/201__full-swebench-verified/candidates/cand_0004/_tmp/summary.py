"""Dump a compact summary of a trajectory: commands + observations + final message.

Usage: python3 _tmp/summary.py <trajectory.json> [max_obs_chars]
"""
import json
import sys

path = sys.argv[1]
max_obs = int(sys.argv[2]) if len(sys.argv) > 2 else 200

with open(path) as f:
    d = json.load(f)

steps = d["rollout"]["trace"]["steps"]
print(f"TASK: {d['score']['task_id']}  reward={d['score']['reward']}  steps={len(steps)}")
print()
for i, s in enumerate(steps):
    src = s.get("source", "?")
    if src in ("system", "user"):
        msg = s.get("message", "")
        print(f"--- [{i}] {src}: {msg[:400]}")
        continue
    # agent step
    tcs = s.get("tool_calls") or []
    for tc in tcs:
        fn = tc.get("function_name", "?")
        args = tc.get("arguments", {})
        cmd = args.get("command", json.dumps(args))
        print(f"[{i}] CMD: {cmd[:500]}")
        obs = s.get("observation") or {}
        results = obs.get("results", [])
        for r in results:
            content = r.get("content", "")
            # content is a JSON string with returncode/output
            try:
                inner = json.loads(content)
                rc = inner.get("returncode")
                out = inner.get("output") or inner.get("output_head") or ""
                print(f"    rc={rc} | {out[:max_obs]}")
            except Exception:
                print(f"    | {content[:max_obs]}")
    msg = s.get("message", "")
    if msg:
        print(f"[{i}] MSG: {msg[:300]}")
print()
print("=== FINAL METRICS ===")
print(json.dumps(d["rollout"]["trace"].get("final_metrics", {}), indent=2)[:500])
