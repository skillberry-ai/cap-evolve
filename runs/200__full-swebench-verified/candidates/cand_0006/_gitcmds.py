import json, os, re, sys

TRAJ = 'trajectories'

# For each failing task, extract the git diff the agent produced (from its own commands' outputs)
# We look for tool_calls whose command is a git commit, and the diff command outputs.

def get_steps(task):
    fn = [f for f in os.listdir(TRAJ) if f.startswith(task)][0]
    d = json.load(open(os.path.join(TRAJ, fn)))
    return (((d.get('rollout') or {}).get('output')) or {}).get('steps') or []

# focus: what did the failing tasks do differently from passing ones?
# Key question 1: did the agent commit its changes? The verifier seems to run `git diff` or apply something.
# Look for how the verifier obtains the patch. In SWE-bench harness, the patch is `git diff` against base commit.
# If the agent COMMITS its change, `git diff` (unstaged vs HEAD) is EMPTY → no patch!

for task in ['django__django-10554', 'django__django-12325', 'django__django-12039', 'django__django-13410']:
    steps = get_steps(task)
    cmds = []
    for s in steps:
        for tc in (s.get('tool_calls') or []):
            c = (tc.get('arguments') or {}).get('command', '')
            cmds.append((s.get('step_id'), c))
    print('=' * 30, task, '=' * 30)
    for sid, c in cmds:
        if 'git ' in c:
            print(f"  [{sid}] {c[:180].replace(chr(10), ' | ')}")
