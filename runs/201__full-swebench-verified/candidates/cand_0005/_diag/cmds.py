"""Extract just the bash commands + brief observation tails from a trajectory."""
import json
import sys

d = json.load(open(sys.argv[1]))
r = d["rollout"]
steps = r["trace"]["steps"]
print(f"### {r['task_id']}  reward={d['score'].get('reward')}  nsteps={len(steps)}")
maxcmd = int(sys.argv[2]) if len(sys.argv) > 2 else 500
maxobs = int(sys.argv[3]) if len(sys.argv) > 3 else 300
for i, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    tcs = s.get("tool_calls") or []
    msg = (s.get("message") or "").strip()
    if msg:
        print(f"\n--[{i}] THINK: {msg[:300]}")
    for tc in tcs:
        args = tc.get("arguments") or {}
        cmd = args.get("command", json.dumps(args)[:maxcmd])
        print(f"--[{i}] CMD: {cmd[:maxcmd]}")
        obs = s.get("observation") or {}
        results = obs.get("results") or []
        for res in results:
            content = res.get("content", "")
            # content is JSON string with returncode/output
            try:
                parsed = json.loads(content)
                out = parsed.get("output", "")
                rc = parsed.get("returncode")
                print(f"      [rc={rc}] {out[:maxobs].strip()!r}")
            except Exception:
                print(f"      {content[:maxobs]!r}")
