import json, sys

def load(task):
    return json.load(open(f'trajectories/{task}__cand_0002__t0.json'))

def obs_of(s):
    try:
        c = s['observation']['results'][0]['content']
        j = json.loads(c)
        return j.get('output', ''), j.get('returncode')
    except Exception:
        return '', None

task = sys.argv[1]
lo, hi = int(sys.argv[2]), int(sys.argv[3])
d = load(task)
steps = (d['rollout'].get('trace') or {}).get('steps') or []
for i, s in enumerate(steps):
    if s.get('source') != 'agent':
        continue
    if not (lo <= i <= hi):
        continue
    for tc in (s.get('tool_calls') or []):
        cmd = (tc.get('arguments') or {}).get('command', '')
        obs, rc = obs_of(s)
        print(f"=== [{i}] rc={rc}")
        print("CMD:", cmd[:1500])
        print("OBS:", (obs or '')[:1500])
        print()
