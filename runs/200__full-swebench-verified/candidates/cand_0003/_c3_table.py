import json, os, glob

TRAJ = 'trajectories'
rows = []
for fn in sorted(os.listdir(TRAJ)):
    if not fn.endswith('.json'): continue
    d = json.load(open(os.path.join(TRAJ, fn)))
    task = fn.split('__cand_0002__')[0]
    sc = d.get('score') or {}
    ro = d.get('rollout') or {}
    vs = ((ro.get('metadata') or {}).get('verifier_stdout') or '')
    steps = ((ro.get('trace') or {}).get('steps')) or []
    rows.append(dict(task=task, reward=sc.get('reward'), feedback=(sc.get('feedback') or '')[:60],
                     nsteps=len(steps), vlen=len(vs), err=ro.get('error')))

rows.sort(key=lambda r: (r['reward'] if r['reward'] is not None else -1))
for r in rows:
    print(f"{r['task']:45s} r={r['reward']!s:5s} steps={r['nsteps']:3d} vlen={r['vlen']:6d} err={r['err']!s:8s} fb={r['feedback']}")
