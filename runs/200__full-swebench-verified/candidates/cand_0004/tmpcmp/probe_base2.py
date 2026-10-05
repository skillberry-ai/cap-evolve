import json, os, sys

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
d = json.load(open(os.path.join(BASE, "tmpcmp", "baseline.json")))
v = d["val"]
print("val type:", type(v).__name__)
if isinstance(v, dict):
    print("val keys:", list(v.keys())[:10])
    items = list(v.items())[:3]
    for k, val in items:
        print(k, "->", json.dumps(val)[:400])
