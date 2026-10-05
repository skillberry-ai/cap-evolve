import json, sys
d = json.load(open(sys.argv[1]))
r = d['rollout']
meta = r.get('metadata') or {}
vs = meta.get('verifier_stdout', '')
n = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
print('reward:', meta.get('harbor_reward'))
print(vs[:n])
print('...TAIL...')
print(vs[-2000:])
