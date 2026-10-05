"""Find full failure detail (traceback) in verifier stdout for specific test."""
import json
import sys

path, needle = sys.argv[1], sys.argv[2]
with open(path) as f:
    d = json.load(f)

vs = d["rollout"]["metadata"].get("verifier_stdout", "")
idx = vs.find(needle)
while idx != -1:
    # print context around
    print(vs[max(0, idx-200):idx+1500])
    print("=" * 60)
    idx = vs.find(needle, idx + 1)
    if idx > len(vs) - 10:
        break
