"""Recover command outputs: trace step N has tool_call + observation; the result is in observation of the FOLLOWING user/env step (optimizer scratch)."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
steps = d["rollout"]["trace"]["steps"]
by_id = {}
for s in steps:
    for tc in s.get("tool_calls") or []:
        by_id[tc.get("tool_call_id")] = (s.get("step_id"), tc)

# also collect all steps that have message starting with '{' (JSON observations from env)
print("total steps:", len(steps))
for i, s in enumerate(steps):
    src = s.get("source")
    msg = (s.get("message") or "")
    if src != "agent" and msg.strip():
        print(f"\n--- step {s.get('step_id')} [{src}] message head:")
        print(msg[:500])
