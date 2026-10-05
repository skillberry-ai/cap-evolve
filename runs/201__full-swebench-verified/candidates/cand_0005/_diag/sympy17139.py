"""Check sympy-17139's final steps in detail - it shows committed=False but had changes."""
import json
import sys

d = json.load(open("trajectories/sympy__sympy-17139__seed__t0.json"))
r = d["rollout"]
steps = (r.get("trace") or {}).get("steps") or []
for i, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    tcs = s.get("tool_calls") or []
    msg = (s.get("message") or "").strip()
    if msg:
        print(f"\n--[{i}] THINK: {msg[:400]}")
    for tc in tcs:
        args = tc.get("arguments") or {}
        cmd = args.get("command", "")
        print(f"--[{i}] CMD: {cmd[:400]}")
        obs = s.get("observation") or {}
        for res in obs.get("results") or []:
            content = res.get("content", "")
            try:
                parsed = json.loads(content)
                out = parsed.get("output", "")
                rc = parsed.get("returncode")
                print(f"      [rc={rc}] {out[:300].strip()!r}")
            except Exception:
                print(f"      {content[:200]!r}")
