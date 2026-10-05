import json, os, sys

TRAJ = "trajectories"

# Check what the verifier actually runs: look at reward_json / verifier_stdout
# for the command line the harness used, to understand the canonical test env.
f = "sphinx-doc__sphinx-9258__seed__t0.json"
d = json.load(open(os.path.join(TRAJ, f)))
md = d["rollout"].get("metadata") or {}
print("REWARD JSON:", json.dumps(md.get("reward_json"), indent=1)[:2500])
vs = md.get("verifier_stdout", "") or ""
print("VERIFIER head:", vs[:2500])
