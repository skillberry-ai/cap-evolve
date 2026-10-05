"""Summarize a trajectory: score, error, output/trace structure."""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)

r = d["rollout"]
s = d["score"]
print("task:", r.get("task_id"))
print("score:", json.dumps(s)[:500])
print("error:", str(r.get("error"))[:300])
tr = r.get("trace")
print("trace type:", type(tr).__name__)
if isinstance(tr, dict):
    print("trace keys:", list(tr.keys()))
    for k, v in tr.items():
        print("  ", k, type(v).__name__, len(v) if hasattr(v, "__len__") else v)
out = r.get("output")
print("output type:", type(out).__name__)
if isinstance(out, str):
    print("output (last 1200):")
    print(out[-1200:])
tc = r.get("tool_calls")
print("tool_calls:", type(tc).__name__, len(tc) if hasattr(tc, "__len__") else "")
md = r.get("metadata")
if isinstance(md, dict):
    print("metadata keys:", list(md.keys()))
