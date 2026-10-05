import json, os, sys, re

TRAJ = 'trajectories'
# KEY QUESTION: what does the final submitted patch contain for sympy-24213?
# The verifier said "Updated 1 path from b86b9b19fd" AFTER the mpmath failure —
# that 'Updated' refers to git checkout of the test file. But CRITICALLY:
# did the agent leave its mpmath/ stub directory in the tree?
# The agent created mpmath/ stub at /testbed. The harness pip install -e . ran fine,
# but then `import sympy` -> `import mpmath.libmp` -> resolved to /testbed/mpmath/libmp.py stub!
# That's why the verifier fails with "No module named 'mpmath.libmp'".
# For sympy-21612, the agent removed mpmath stubs ("rm -rf mpmath mpmath.py").

# Let me check sympy-21612's step 21.
fn = os.path.join(TRAJ, 'sympy__sympy-21612__cand_0002__t0.json')
d = json.load(open(fn))
out = d['rollout']['output']
for s in out['steps']:
    if s.get('source') != 'agent':
        continue
    for c in (s.get('tool_calls') or []):
        args = c.get('arguments') or c.get('input') or {}
        cmd = args.get('command') if isinstance(args, dict) else None
        if cmd and ('rm ' in cmd or 'git status' in cmd):
            print(f"[{s.get('step_id')}] {cmd[:200]}")
            print("OBS:", str(s.get('observation'))[:300])
            print()
