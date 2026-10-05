"""Dump the commands of every step of a trajectory, with truncated outputs."""
import json
import sys

path = sys.argv[1]
outlen = int(sys.argv[2]) if len(sys.argv) > 2 else 300
d = json.load(open(path))
r = d["rollout"]
steps = r["trace"]["steps"]
for s in steps:
    src = s.get("source")
    if src != "agent":
        continue
    tcs = s.get("tool_calls") or []
    for tc in tcs:
        cmd = tc.get("arguments", {}).get("command", "")
        obs = tc.get("observation", {}).get("results", [])
        print(f"### {s.get('step_id')}: $ {cmd}")
        for o in obs:
            c = o.get("content", "")
            try:
                j = json.loads(c)
                rc = j.get("returncode")
                out = j.get("output") or j.get("output_head") or ""
                print(f"    [rc={rc}] {str(out)[:outlen]}".replace("\n", "\n    "))
            except Exception:
                print(f"    {str(c)[:outlen]}")
    if not tcs:
        msg = s.get("message", "")
        if msg:
            print(f"### {s.get('step_id')}: (no tool) {msg[:200]}")
