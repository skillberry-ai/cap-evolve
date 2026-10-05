import json, os, sys

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

task = sys.argv[1]
d = load(task)
steps = d['rollout']['trace']['steps']
for s in steps[:6]:
    src = s.get('source')
    sid = s.get('step_id')
    msg = s.get('message') or ''
    print(f"=== [{sid}] source={src} len={len(msg)}")
    print(msg[:1500])
    print()
