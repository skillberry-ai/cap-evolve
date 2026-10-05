import json, os, sys

TRAJ = "trajectories"
t = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
vs = (d['rollout'].get('metadata') or {}).get('verifier_stdout', '') or ''
# print the FIRST 120 lines to see the run/eval setup portion
lines = [ln for ln in vs.splitlines() if 'Creating table' not in ln and 'Applying' not in ln]
print("\n".join(lines[:100]))
