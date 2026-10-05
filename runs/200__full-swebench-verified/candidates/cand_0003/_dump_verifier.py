import json, sys, os

TRAJ = 'trajectories'
fn = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, fn)))
out = ((d.get('rollout') or {}).get('output')) or {}
steps = out.get('steps') or []
meta = ((d.get('rollout') or {}).get('metadata')) or {}
vs = meta.get('verifier_stdout', '')
print("VERIFIER_STDOUT tail:")
print(vs[-2500:])
print()
print("VERIFIER_STDERR:", meta.get('verifier_stderr', '')[:1500])
