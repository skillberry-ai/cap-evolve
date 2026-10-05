import json
fn = 'trajectories/pylint-dev__pylint-4661__cand_0002__t0.json'
d = json.load(open(fn))
vs = d['rollout']['metadata']['verifier_stdout']
print(vs[:3000])
