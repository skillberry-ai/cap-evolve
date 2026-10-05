import json, os, sys

TRAJ = 'trajectories'
def obs_of(s):
    obs = s.get('observation') or {}
    try:
        c = obs['results'][0]['content']
        j = json.loads(c)
        return j.get('output', ''), j.get('returncode')
    except Exception:
        return '', None

t = sys.argv[1]
fn = os.path.join(TRAJ, f"{t}__cand_0002__t0.json")
d = json.load(open(fn))
out = (d.get('rollout') or {}).get('output') or {}
steps = out.get('steps') or []
for idx, s in enumerate(steps):
    if s.get('source') != 'agent':
        continue
    for tc in (s.get('tool_calls') or []):
        cmd = (tc.get('arguments') or {}).get('command', '')
        obs, rc = obs_of(s)
        if any(m in cmd for m in ('pytest', 'py.test', 'runtests.py', '/bin/test', 'bin/test', 'unittest')):
            print(f"### step {idx} rc={rc}")
            print('CMD:', cmd[:600].replace('\n', ' ;; '))
            print('OUT:', (obs or '')[:1200].replace('\n', ' | '))
            print()
