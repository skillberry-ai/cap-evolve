import json, os

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
d = json.load(open(os.path.join(BASE, "tmpcmp", "baseline.json")))
v = d["val"]["per_task"]
print(type(v).__name__, len(v))
if isinstance(v, dict):
    for k in list(v)[:5]:
        print(k, json.dumps(v[k])[:300])
elif isinstance(v, list):
    for x in v[:5]:
        print(json.dumps(x)[:300])
