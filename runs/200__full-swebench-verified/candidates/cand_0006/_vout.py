import json, os, sys

TRAJ = "trajectories"

t = sys.argv[1]
d = json.load(open(os.path.join(TRAJ, f"{t}__seed__t0.json")))
md = d["rollout"].get("metadata") or {}
vs = md.get("verifier_stdout", "") or ""
print("VERIFIER_STDOUT len:", len(vs))
print(vs[:6000])
