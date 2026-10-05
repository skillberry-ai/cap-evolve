import json, os, sys

TRAJ = "trajectories"
t = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
vs = (d['rollout'].get('metadata') or {}).get('verifier_stdout', '') or ''
# The SWEBench harness computes the patch: look for the git checkout/apply lines around "Updated N paths"
lines = vs.splitlines()
for i, ln in enumerate(lines):
    if 'Updated' in ln and 'path' in ln:
        print("CONTEXT around line", i)
        for l2 in lines[max(0, i-15):i+3]:
            print("   ", l2[:200])
        print()
