import json, os, sys, re

TRAJ = 'trajectories'

# For FAILING tasks: was the model patch actually applied by the verifier?
# The SWE-bench harness applies the MODEL patch with `git apply` then the TEST patch.
# But here we see no 'git apply' for most failing tasks → the model patch may have
# been EMPTY (agent committed its changes, so `git diff` produced nothing).
# Let's check: in SWE-bench, model patch = `git diff` in the container after the agent finishes.
# If agent ran `git commit`, `git diff` is empty!

# Confirm by looking at what the agent did at the end + the verifier's 'Updated N paths' line.
# In passing tasks we saw 'Updated 1 path from <sha>' — that's from `git apply` of... something.
# Actually 'Updated 1 path from b3f2ad248a' appears in FAILING 10554 too. That's the TEST patch apply (checkout?).

# The key question: how is the final model patch extracted? Look at the runner (mini-swe-agent).
# The trajectory metadata has 'verifier_stdout' only. But we saw in passing tasks:
#   '+ git apply --check /tmp/test_patch.diff' — so the verifier applies test_patch.diff.
# For the model patch: SWE-bench harness usually does `git diff` BEFORE applying the test patch,
# or the agent's diff is extracted via `git diff HEAD` similar.

# Let's test the hypothesis on behavior differences: in failing tasks the agent COMMITTED;
# in passing tasks it also committed (12039 committed!) — so that's not the discriminator.

# Actually for 12039 (passing), agent committed too. So committing is fine.

# The failing tasks differ in the actual TEST outcomes. Let's tabulate: for each failing task,
# the last test-run summary (Ran X tests ... FAILED/OK) to see if tests ran at all.

for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith('.json'):
        continue
    d = json.load(open(os.path.join(TRAJ, fn)))
    task = fn.replace('__seed__t0.json', '')
    reward = (d.get('score') or {}).get('reward')
    if reward != 0.0:
        continue
    out = ((d.get('rollout') or {}).get('output')) or {}
    steps = out.get('steps') or []
    if not steps:
        continue
    meta = ((d.get('rollout') or {}).get('metadata')) or {}
    vs = meta.get('verifier_stdout', '') or ''
    idx = vs.find('SWEBench results starts here')
    head = vs[:idx] if idx >= 0 else vs
    lines = head.splitlines()
    summary = [l for l in lines if re.match(r'^(Ran \d+ tests|OK|FAILED)', l)]
    n_err = sum(1 for l in lines if l.startswith('ERROR:') or l.startswith('FAIL:'))
    print(f"{task:45s} {summary} errlines={n_err}")
