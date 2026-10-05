import json, sys
d = json.load(open(sys.argv[1]))
vs = (d['rollout'].get('metadata') or {}).get('verifier_stdout','')
# print 1200 chars around the first 'FAILED' occurrence
i = vs.find('FAILED')
print(vs[max(0,i-200):i+3000] if i>=0 else 'none')
