"""Extract the agent's actual bash commands from a mini-swe-agent ATIF trajectory."""
import json
import re
import sys

d = json.load(open(sys.argv[1]))
print("### top keys:", list(d.keys()))
sc = d.get("score", {})
print("### score:", json.dumps(sc)[:800])
tr = d.get("rollout") or {}
print("### rollout keys:", list(tr.keys()))
trace = tr.get("trace") or {}
print("### trace keys:", list(trace.keys()))
steps = trace.get("steps") or []
print("### n steps:", len(steps))
if steps:
    print("### step0 keys:", list(steps[0].keys()))
    print("### step0 sample:", json.dumps(steps[0])[:600])
