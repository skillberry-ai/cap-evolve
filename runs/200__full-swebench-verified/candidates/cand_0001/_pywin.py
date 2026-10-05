import json, os, sys
TRAJ = "trajectories"
t = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
vs = (d['rollout'].get('metadata') or {}).get('verifier_stdout', '') or ''
print("TOTAL LEN", len(vs))
n = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
o = int(sys.argv[3]) if len(sys.argv) > 3 else 0
print(vs[o:o+n])
