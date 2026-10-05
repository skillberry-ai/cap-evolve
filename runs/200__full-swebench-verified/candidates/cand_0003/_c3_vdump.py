import json, os

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

d = load('django__django-10554')
ro = d['rollout']
steps = ro['trace']['steps']
print("VERIFIER STDOUT (first 5000):")
print(ro['metadata']['verifier_stdout'][:5000])
