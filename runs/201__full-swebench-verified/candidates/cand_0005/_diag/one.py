"""Check sympy-18211 and sympy-21612 and pytest-10356 (failing) final steps."""
import json
import sys

name = sys.argv[1]
f = f"trajectories/{name}__seed__t0.json"
d = json.load(open(f))
r = d["rollout"]
steps = (r.get("trace") or {}).get("steps") or []
print(f"### {name} reward={d['score'].get('reward')}")
for i, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    tcs = s.get("tool_calls") or []
    msg = (s.get("message") or "").strip()
    if msg:
        print(f"\n--[{i}] THINK: {msg[:350]}")
    for tc in tcs:
        args = tc.get("arguments") or {}
        cmd = args.get("command", "")
        print(f"--[{i}] CMD: {cmd[:350]}")
        obs = s.get("observation") or {}
        for res in obs.get("results") or []:
            content = res.get("content", "")
            try:
                parsed = json.loads(content)
                out = parsed.get("output", "")
                rc = parsed.get("returncode")
                print(f"      [rc={rc}] {out[:250].strip()!r}")
            except Exception:
                print(f"      {content[:200]!r}")
