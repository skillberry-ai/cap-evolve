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
n = int(sys.argv[2]) if len(sys.argv) > 2 else 3
d = load(task)
steps = d['rollout']['trace']['steps']
# print last n agent steps with observation excerpts
agent_steps = [s for s in steps if s.get('source') == 'agent']
for s in agent_steps[-n:]:
    sid = s.get('step_id')
    tcs = s.get('tool_calls') or []
    for tc in tcs:
        cmd = (tc.get('arguments') or {}).get('command', '')
        print(f"=== [{sid}] CMD:\n{cmd[:1500]}")
    out, rc = obs_of(s)
    print(f"--- [{sid}] OBS (rc={rc}):\n{out[:2500]}")
    print()
