import json, os

TRAJ = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004/trajectories"

# Print the head of verifier_stdout for a sympy task to see how the harness runs tests
for name in ("sympy__sympy-15599__seed__t0.json", "sphinx-doc__sphinx-8035__seed__t0.json"):
    data = json.load(open(os.path.join(TRAJ, name)))
    md = data["rollout"].get("metadata") or {}
    so = md.get("verifier_stdout") or ""
    print("=" * 100)
    print(name)
    print(so[:3500])
