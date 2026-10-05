import json, os, sys

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

# How does the model patch get extracted? Look for 'model_patch' or 'git diff' at end of agent's commands
# mini-swe-agent extracts the model patch via `git add -A && git diff --cached base_commit`.
# Let's check if the agent's final command in cand_0002 traces matches this, or whether the harness does it.
# Compare: does the agent ever run `git diff --cached` or similar?
PASSING = ["django__django-12039","django__django-12276","sympy__sympy-17139"]
FAILING = ["django__django-10554","astropy__astropy-13453"]
for task in PASSING + FAILING:
    d = load(task)
    steps = d['rollout']['trace']['steps']
    agent_steps = [s for s in steps if s.get('source') == 'agent']
    print(f"### {task}")
    for s in agent_steps:
        for tc in (s.get('tool_calls') or []):
            cmd = (tc.get('arguments') or {}).get('command','')
            if 'git diff --cached' in cmd or 'git diff HEAD' in cmd or cmd.strip() == 'git diff' or 'git add -A' in cmd:
                print(f"    [{s.get('step_id')}] {cmd[:150]}")
    print()
