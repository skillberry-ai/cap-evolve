"""Print each agent step's bash command + observation tail for a trajectory."""
import json
import sys

d = json.load(open(sys.argv[1]))
steps = d["rollout"]["trace"]["steps"]
obs_len = int(sys.argv[2]) if len(sys.argv) > 2 else 300
cmd_len = int(sys.argv[3]) if len(sys.argv) > 3 else 500
print(f"### {d['rollout']['task_id']}  reward={d['score'].get('reward')}")
for i, s in enumerate(steps):
    if s.get("source") != "agent":
        continue
    tcs = s.get("tool_calls") or []
    thought = (s.get("message") or "").strip()
    if thought and len(tcs) == 0:
        print(f"\n[{i}] THINK: {thought[:250]}")
    for tc in tcs:
        cmd = (tc.get("arguments") or {}).get("command", "")
        print(f"\n[{i}] CMD: {cmd[:cmd_len]}")
        obs = s.get("observation") or {}
        for r in obs.get("results", []):
            c = r.get("content", "")
            try:
                j = json.loads(c)
                rc = j.get("returncode")
                out = j.get("output") or j.get("output_head") or ""
                if j.get("output_tail"):
                    out = j.get("output_tail")
                print(f"    rc={rc} OUT: {str(out)[-obs_len:]}")
            except Exception:
                print(f"    RAW: {c[:obs_len]}")
