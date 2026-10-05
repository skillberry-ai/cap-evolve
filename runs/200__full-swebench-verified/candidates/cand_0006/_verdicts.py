import json, os, re

TRAJ = 'trajectories'

# For each FAILING task: extract (a) the commands that modified files, (b) whether
# a git commit happened, (c) the final diff the verifier would see, (d) verifier output tail.
FAILING = []
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith('.json'):
        continue
    d = json.load(open(os.path.join(TRAJ, fn)))
    if ((d.get('score') or {}).get('reward') or 0) > 0:
        continue
    out = ((d.get('rollout') or {}).get('output')) or {}
    steps = out.get('steps') or []
    if not steps:
        continue
    task = fn.replace('__seed__t0.json', '')
    meta = ((d.get('rollout') or {}).get('metadata')) or {}
    vs = meta.get('verifier_stdout', '') or ''
    # Pull the SWEBench results section
    m = re.search(r'SWEBench results starts here(.*?)SWEBench results ends here', vs, re.S)
    verdict = m.group(1).strip()[:200] if m else '???'
    # find test output lines like FAILED / ERROR / passed / failed counts
    lines = vs.splitlines()
    tail = '\n'.join(lines[-15:])
    FAILING.append((task, verdict))

for t, v in FAILING:
    print(f"{t}: {v}")
