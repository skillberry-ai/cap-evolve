import json, sys
d = json.load(open(sys.argv[1]))
vs = (d['rollout'].get('metadata') or {}).get('verifier_stdout','')
i = vs.find('____ test_concise')
j = vs.find('_ test_')
k = vs.find('____')
if i < 0:
    i = vs.find('____')
print(vs[i:i+4000] if i >= 0 else vs[:1500])
