import json, os, sys

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

# What does the verifier do for django__django-12039 (passing, updated=[])?
# The agent's patch must be applied some other way. Let's look at the FIRST 2000 chars.
d = load('django__django-12039')
vs = d['rollout']['metadata']['verifier_stdout']
# find beginning markers
i = vs.find('SWEBench')
print("len:", len(vs))
# Print the last 3000 chars (verifier script trace often at end)
print(vs[-3000:])
