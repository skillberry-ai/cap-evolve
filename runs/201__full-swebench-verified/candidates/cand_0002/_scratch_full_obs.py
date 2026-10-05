"""Extract commands + FULL parsed outputs (optimizer scratch)."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
steps = d["rollout"]["trace"]["steps"]
for s in steps:
    for tc in s.get("tool_calls") or []:
        cmd = (tc.get("arguments") or {}).get("command") or ""
        res = ((tc.get("observation") or {}).get("results") or [])
        content = res[0].get("content", "") if res else ""
        out = ""
        rc = ""
        try:
            cj = json.loads(content)
            rc = cj.get("returncode")
            out = (cj.get("output") or "")
        except Exception:
            out = content
        if isinstance(out, str) and len(out) > 1200:
            out = out[:600] + "\n...[snip]...\n" + out[-400:]
        print(f"\n===== [{s.get('step_id')}] rc={rc} CMD: {cmd[:220]}")
        print(out)
