import json, os, sys

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

# The mini-swe-agent convention: final output is extracted from the last agent
# message OR from `git diff` in the harness. Let's check the `output` section:
d = load('sympy__sympy-15599')
ro = d['rollout']
out = ro.get('output') or {}
print("OUTPUT keys:", list(out.keys()))
steps = out.get('steps') or []
print("output.steps:", len(steps))
# check final agent message in output.steps
agent_steps = [s for s in steps if s.get('source') == 'agent']
print("last 3 output agent steps:")
for s in agent_steps[-3:]:
    print("step_id:", s.get('step_id'), "msg len:", len(s.get('message') or ''))
    print((s.get('message') or '')[:500])
    print('---')
# any 'final' / 'message' at top of output?
for k in ('message', 'final', 'final_message'):
    if k in out:
        print(f"output.{k}:", str(out[k])[:500])
# check rollout.output.agent
ag = out.get('agent') or {}
print("agent keys:", list(ag.keys()))
