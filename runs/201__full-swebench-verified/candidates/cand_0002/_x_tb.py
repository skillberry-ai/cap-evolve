import json, sys

# Show the pytest traceback section (long form) for failures in verifier stdout.
d = json.load(open(sys.argv[1]))
r = d['rollout']
meta = r.get('metadata') or {}
vs = meta.get('verifier_stdout', '')
# Find "=== FAILURES ===" section
idx = vs.find('=== FAILURES ===')
if idx == -1:
    idx = vs.find('FAILURES')
print(vs[idx:idx+6000] if idx != -1 else '(no FAILURES section)')
