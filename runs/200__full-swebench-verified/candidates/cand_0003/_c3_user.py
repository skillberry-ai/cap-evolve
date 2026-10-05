import json, os, sys

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

def obs_of(step):
    obs = step.get('observation')
    if not obs: return '', None
    try:
        c = obs['results'][0]['content']
        j = json.loads(c)
        return j.get('output', ''), j.get('returncode')
    except Exception:
        return '', None

task = sys.argv[1]
d = load(task)
steps = d['rollout']['trace']['steps']
# find first user step (the task statement)
for s in steps:
    if s.get('source') == 'user':
        print("USER TASK (first 3000 chars):")
        print((s.get('message') or '')[:3000])
        break
