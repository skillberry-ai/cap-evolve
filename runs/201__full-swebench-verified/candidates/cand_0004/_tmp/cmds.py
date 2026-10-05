"""Print per-step tool calls (commands) and observation tails for a trajectory."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
steps = d["rollout"]["trace"]["steps"]
print(f"### {d['rollout']['task_id']}  reward={d['score'].get('reward')}  steps={len(steps)}")
for s in steps:
    msg = s.get("message", {})
    if not isinstance(msg, dict):
        continue
    role = s.get("source", "?")
    tcs = msg.get("tool_calls")
    if tcs:
        for tc in tcs:
            fn = tc.get("function", {})
            args = fn.get("arguments", "")
            if isinstance(args, str):
                try:
                    a = json.loads(args)
                    cmd = a.get("command", a)
                except Exception:
                    cmd = args
            else:
                cmd = args
            print(f"\n>>> [{role} CMD] {str(cmd)[:600]}")
    elif role in ("tool", "assistant"):
        c = msg.get("content", "")
        if c:
            print(f"<<< OBS: {str(c)[:450]}")
