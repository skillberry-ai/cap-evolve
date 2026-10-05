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
agent_steps = [s for s in steps if s.get('source') == 'agent']
# print commands with rc != 0 and short excerpt
for s in agent_steps:
    out, rc = obs_of(s)
    for tc in (s.get('tool_calls') or []):
        cmd = (tc.get('arguments') or {}).get('command','')
        if rc not in (0, None):
            print(f"=== [{s.get('step_id')}] rc={rc} CMD: {cmd[:150]}")
            print(f"    OBS: {out[:400]}")
            print()
