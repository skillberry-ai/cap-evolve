import json, os, sys

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

# Extract the FINAL agent message (the "final output" containing the patch?) or check output message
for task in ['sympy__sympy-15599', 'django__django-10554']:
    d = load(task)
    steps = d['rollout']['trace']['steps']
    # The last agent step before COMPLETE_TASK: its message content
    agent_msgs = [s for s in steps if s.get('source') == 'agent']
    # find the step that contains COMPLETE_TASK
    for s in agent_msgs:
        tcs = s.get('tool_calls') or []
        for tc in tcs:
            cmd = (tc.get('arguments') or {}).get('command','')
            if 'COMPLETE_TASK' in cmd:
                print(f"### {task}: message of COMPLETE step:")
                print((s.get('message') or '')[:1000])
                break
