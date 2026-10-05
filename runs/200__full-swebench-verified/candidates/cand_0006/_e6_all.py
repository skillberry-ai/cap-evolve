import json, os, sys

TRAJ = 'trajectories'
FAILING = set("""astropy__astropy-13453 django__django-10554 django__django-11555 django__django-12325
django__django-12708 django__django-14007 django__django-14376 django__django-15629 django__django-16032
django__django-16667""".split())

rows = []
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith('.json'):
        continue
    d = json.load(open(os.path.join(TRAJ, fn)))
    task = fn.rsplit('__', 2)[0]
    sc = d.get('score') or {}
    reward = sc.get('reward')
    r = d.get('rollout') or {}
    out = (r.get('output') or {})
    steps = out.get('steps') or []
    md = r.get('metadata') or {}
    vs = md.get('verifier_stdout', '') or ''
    rows.append((task, reward, len(steps), vs))

for t, rw, ns, vs in sorted(rows, key=lambda x: (x[1] or 0, x[0])):
    mark = 'FAIL' if (rw or 0) < 0.5 else 'pass'
    print(f"{mark} {t:45s} r={rw} steps={ns} vstdout_len={len(vs)}")
