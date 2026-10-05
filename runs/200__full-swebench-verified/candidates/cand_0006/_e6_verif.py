import json, os, sys

TRAJ = 'trajectories'
fn = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, fn)))
md = d['rollout'].get('metadata') or {}
vs = md.get('verifier_stdout', '') or ''
ve = md.get('verifier_stderr', '') or ''
print("===== VERIFIER STDOUT =====")
print(vs)
print("===== VERIFIER STDERR (first 3000) =====")
print(ve[:3000])
