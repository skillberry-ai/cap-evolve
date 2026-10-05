"""Find why patches fail: compare agent patch vs expected gold patch (optimizer scratch).

Downloads nothing; uses the local SWE-bench data if present, else prints top-level keys.
"""
import json
import sys

path = sys.argv[1]
with open(path) as f:
    d = json.load(f)
print("top keys:", list(d.keys()))
score = d["score"]
print("score keys:", list(score.keys()))
print("score:", json.dumps({k: (v if not isinstance(v, str) or len(v) < 200 else v[:200]) for k, v in score.items()})[:1500])
ro = d.get("rollout") or {}
print("rollout keys:", list(ro.keys()))
out = ro.get("output")
if isinstance(out, str):
    print("--- rollout.output (len", len(out), ") head ---")
    print(out[:1500])
