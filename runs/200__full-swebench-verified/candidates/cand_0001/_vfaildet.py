import json, os, sys

TRAJ = "trajectories"
t = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
vs = (d['rollout'].get('metadata') or {}).get('verifier_stdout', '') or ''
lines = vs.splitlines()
# Find the first FAILURES section and print details for the first 2 failed tests
try:
    i = lines.index("=================================== FAILURES ===================================")
except ValueError:
    # sympy style: print around the FAIL marker
    for j, ln in enumerate(lines):
        if '[FAIL]' in ln or 'FAILED' in ln:
            print("\n".join(lines[max(0,j-5):j+40]))
            break
    sys.exit()
print("\n".join(lines[i:i+80]))
