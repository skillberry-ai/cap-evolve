"""Print full observation content for selected step ids (optimizer scratch)."""
import json
import sys

path, want = sys.argv[1], set(int(x) for x in sys.argv[2:])
d = json.load(open(path))
steps = d["rollout"]["trace"]["steps"]
for s in steps:
    if s.get("step_id") in want:
        for tc in s.get("tool_calls") or []:
            cmd = (tc.get("arguments") or {}).get("command") or ""
            res = ((tc.get("observation") or {}).get("results") or [])
            content = res[0].get("content", "") if res else ""
            print(f"===== [{s.get('step_id')}] CMD: {cmd[:200]}")
            print(content[:2500])
            print()
