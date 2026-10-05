"""Dump the input issue text + the final committed patch for a trajectory."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)

print("### TASK:", d["score"]["task_id"], "reward:", d["score"]["reward"])
print("### ISSUE TEXT (input):")
print(d["input"][:3500])
print("### ...")

steps = d["rollout"]["trace"]["steps"]
# find last git diff/show output
print("\n### LAST DIFF-LIKE OUTPUTS:")
for i, s in enumerate(steps):
    tcs = s.get("tool_calls") or []
    for tc in tcs:
        cmd = tc.get("arguments", {}).get("command", "")
        if "git --no-pager diff" in cmd or "git --no-pager show" in cmd:
            obs = s.get("observation") or {}
            for r in obs.get("results", []):
                content = r.get("content", "")
                try:
                    inner = json.loads(content)
                    out = inner.get("output") or ""
                except Exception:
                    out = content
                if out.strip():
                    print(f"\n--- [{i}] CMD: {cmd[:120]}")
                    print(out[:3000])
