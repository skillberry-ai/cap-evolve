import json, sys

# Show context around FAILED lines in verifier stdout.
d = json.load(open(sys.argv[1]))
r = d['rollout']
meta = r.get('metadata') or {}
vs = meta.get('verifier_stdout', '')
lines = vs.splitlines()
for i, ln in enumerate(lines):
    if ln.startswith('FAILED') or ('AssertionError' in ln) or ('Error' in ln and 'FAILED' not in ln and 'PASSED' not in ln):
        print('>>>', ln[:250])
        for j in range(max(0, i-6), min(len(lines), i+2)):
            print('   ', lines[j][:250])
        print()
