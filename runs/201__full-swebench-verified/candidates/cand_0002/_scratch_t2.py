import json
d = json.load(open("trajectories/sympy__sympy-21612__seed__t0.json"))
steps = d["rollout"]["trace"]["steps"]
# find any steps whose source != agent OR that follow tool calls: what do observation steps look like?
from collections import Counter
c = Counter(s.get("source") for s in steps)
print(c)
# print message of the steps AFTER step 19, 20 (agent responses react to output)
ids = [s.get("step_id") for s in steps]
for i, s in enumerate(steps):
    sid = s.get("step_id")
    if sid in ("21", "22"):
        print(f"\n=== step {sid} source={s.get('source')} message:")
        print((s.get("message") or "")[:1500])
