import json, os, re

TRAJ = 'trajectories'

rows = []
for f in sorted(os.listdir(TRAJ)):
    if not f.endswith('.json'):
        continue
    d = json.load(open(os.path.join(TRAJ, f)))
    ro = d.get('rollout')
    if not ro:
        continue
    meta = ro.get('metadata') or {}
    vs = meta.get('verifier_stdout', '') or ''
    reward = (d.get('score') or {}).get('reward')
    envs = set(re.findall(r'/opt/miniconda3/envs/(\S*?)/bin', vs))
    envs2 = set(re.findall(r'/opt/miniconda3/envs/([A-Za-z0-9_.-]+)/lib', vs))
    has_runtests = 'runtests.py' in vs
    has_pytest_style = re.search(r'=+ .{0,4}failed|short test summary|passed', vs) is not None
    rows.append((f.replace('__cand_0002__t0.json', ''), reward, sorted(envs | envs2), has_runtests))

n_testbed = sum(1 for r in rows if r[2] == ['testbed'])
print(f"tasks whose verifier uses envs/testbed: {n_testbed}/{len(rows)}")
for r in rows:
    if r[2] != ['testbed']:
        print("  NON-TESTBED:", r[0], r[2], "runtests.py in vs:", r[3])
# which repos use runtests.py
print("\nrepos with runtests.py in verifier output:")
for r in rows:
    if r[3]:
        print("  ", r[0], r[1])
