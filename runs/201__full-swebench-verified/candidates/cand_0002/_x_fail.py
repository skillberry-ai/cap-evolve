import json, sys

# Search verifier_stdout for FAILED lines and the harness verdict.
d = json.load(open(sys.argv[1]))
r = d['rollout']
meta = r.get('metadata') or {}
vs = meta.get('verifier_stdout', '')
print('reward:', meta.get('harbor_reward'))
lines = vs.splitlines()
for i, ln in enumerate(lines):
    if ('FAILED' in ln or 'ERROR' in ln or 'failed' in ln or 'SWEBench results' in ln):
        # print with a bit of context for FAILED test lines
        print(ln[:300])
