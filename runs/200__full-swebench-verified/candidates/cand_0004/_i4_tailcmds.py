import json, os, sys

TRAJ = 'trajectories'

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + '__'):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667",
]

def obs_of(s):
    if not s.get("observation"):
        return "", None
    try:
        c = s["observation"]["results"][0]["content"]
        j = json.loads(c)
        return j.get("output", "") or "", j.get("returncode")
    except Exception:
        return "", None

# For each failing task: did the agent run the FAILED TO PASS tests (from verifier stdout) before finishing?
# Extract the failing test names from verifier_stdout and check if the agent's own test runs covered them.
import re
for task in FAILING:
    d = load(task)
    meta = ((d.get('rollout') or {}).get('metadata')) or {}
    vs = meta.get('verifier_stdout', '') or ''
    steps = (d.get('rollout') or {}).get('trace', {}).get('steps') or []
    # failed test ids in verifier
    failed_tests = set(re.findall(r'FAILED (\S+::\S+)', vs)) | set(re.findall(r'ERROR: (\S+) \(', vs))
    # agent's commands
    agent_cmds = []
    last_test_cmds = []
    n_edit_after = 0
    finish_idx = None
    for i, s in enumerate(steps):
        if s.get('source') != 'agent':
            continue
        for tc in (s.get('tool_calls') or []):
            c = (tc.get('arguments') or {}).get('command', '')
            agent_cmds.append((i, c))
            if 'COMPLETE_TASK_AND_SUBMIT' in c:
                finish_idx = len(agent_cmds) - 1
    print("=" * 100)
    print("TASK", task)
    print("verifier failed tests:", sorted(failed_tests)[:6])
    print(f"total agent cmds: {len(agent_cmds)}; finish at {finish_idx}")
    print("LAST 12 commands:")
    for (i, c) in agent_cmds[-12:]:
        obs, rc = None, None
        # find observation for the step
        print(f"  step{i}: rc? {c[:180]}")
