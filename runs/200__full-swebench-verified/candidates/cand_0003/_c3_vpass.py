import json, os, sys

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

# What does the verifier do FIRST? Look at the beginning of verifier_stdout for a PASSING task
d = load('django__django-12039')
vs = d['rollout']['metadata']['verifier_stdout']
print(vs[:4000])
