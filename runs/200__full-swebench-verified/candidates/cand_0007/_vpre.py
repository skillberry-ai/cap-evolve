import json, sys

fn = sys.argv[1]
d = json.load(open(fn))
meta = ((d.get('rollout') or {}).get('metadata')) or {}
vs = meta.get('verifier_stdout', '')
idx = vs.find('git apply')
print('git apply at index:', idx)
print('---- content before git apply ----')
print(vs[:idx][:4000])
