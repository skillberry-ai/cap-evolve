import json, os, sys

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

# Look at observation structure of a command step to understand return codes; then find how many total commands were run
# and whether the final message includes a diff. Also look at the "system" step count and the last system message.
d = load('sympy__sympy-15599')
steps = d['rollout']['trace']['steps']
# print all step sources
from collections import Counter
print(Counter(s.get('source') for s in steps))
# print any system message after the first
for s in steps:
    if s.get('source') == 'system' and s.get('step_id', 0) > 1:
        print(f"[{s.get('step_id')}]", (s.get('message') or '')[:300])
# what does observation look like
s = steps[5]
print(json.dumps(s, indent=1)[:2500])
