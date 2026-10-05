"""Print a compact per-step view of a trajectory: role, tool call / command, output tail."""
import json
import sys

path = sys.argv[1]
cmdlen = int(sys.argv[2]) if len(sys.argv) > 2 else 400
outlen = int(sys.argv[3]) if len(sys.argv) > 3 else 700
with open(path) as f:
    d = json.load(f)
steps = d["rollout"]["trace"]["steps"]
print(f"### {d['rollout']['task_id']}  reward={d['score'].get('reward')}  steps={len(steps)}")
for s in steps:
    msg = s.get("message", {})
    role = s.get("source", "?")
    if isinstance(msg, str):
        print(f"[{role}] {msg[:cmdlen]}")
        continue
    content = msg.get("content", "")
    if isinstance(content, list):
        for c in content:
            if isinstance(c, dict):
                t = c.get("text") or c.get("input") or ""
                print(f"[{role}/{c.get('type')}] {str(t)[:cmdlen]}")
    else:
        tcs = msg.get("tool_calls")
        if tcs:
            for tc in tcs:
                fn = tc.get("function", {})
                print(f"[{role}->CALL {fn.get('name')}] {str(fn.get('arguments'))[:cmdlen]}")
        else:
            txt = str(content)
            print(f"[{role}] {txt[:outlen]}")
    print("---")
