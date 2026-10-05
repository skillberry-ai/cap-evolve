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
# print last N agent steps with commands
N = int(sys.argv[2]) if len(sys.argv) > 2 else 12
agent_steps = [(i, s) for i, s in enumerate(steps) if s.get('source') == 'agent']
for i, s in agent_steps[-N:]:
    msg = (s.get('message') or '')
    print(f"--- step {i} ---")
    if msg:
        print('MSG:', msg[:400].replace('\n', ' | '))
    for tc in (s.get('tool_calls') or []):
        cmd = (tc.get('arguments') or {}).get('command', '')
        print('CMD:', cmd[:400].replace('\n', ' ;; '))
    obs, rc = obs_of(s)
    if obs or rc is not None:
        print(f"OBS rc={rc}:", (obs or '')[:400].replace('\n', ' | '))
    print()
