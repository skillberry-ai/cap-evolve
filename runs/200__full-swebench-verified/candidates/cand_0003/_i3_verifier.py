import json, os, sys

task = sys.argv[1]
fn = f'trajectories/{task}__cand_0002__t0.json'
d = json.load(open(fn))
r = d['rollout']
meta = r.get('metadata') or {}
keys = list(meta.keys())
print("META KEYS:", keys)
vs = meta.get('verifier_stdout', '') or ''
print("verifier_stdout len:", len(vs))
print(vs[:6000])
