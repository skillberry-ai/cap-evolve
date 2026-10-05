"""Show raw step structure."""
import json
import sys

d = json.load(open(sys.argv[1]))
steps = d["rollout"]["trace"]["steps"]
for i, s in enumerate(steps[:6]):
    print("STEP", i, "source=", s.get("source"))
    m = s.get("message", {})
    print("  msg type:", type(m).__name__)
    if isinstance(m, dict):
        print("  keys:", list(m.keys()))
        print("  content:", str(m.get("content"))[:400])
        print("  tool_calls:", str(m.get("tool_calls"))[:400])
    print()
