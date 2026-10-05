import json, os, re

TRAJ = 'trajectories'

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + '__'):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

def obs_of(s):
    if not s.get("observation"):
        return "", None
    try:
        c = s["observation"]["results"][0]["content"]
        j = json.loads(c)
        return j.get("output", "") or "", j.get("returncode")
    except Exception:
        return "", None

# For every failing task, print the exact failing test ids from the verifier and
# whether the agent EVER ran a command mentioning any of those test names.
FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667",
]
for task in FAILING:
    d = load(task)
    meta = ((d.get('rollout') or {}).get('metadata')) or {}
    vs = meta.get('verifier_stdout', '') or ''
    # test command line(s) the verifier ran — look for lines with 'python -m' or 'runtests' or 'pytest' near top? Also 'Ran X tests'
    # Extract FAILED/ERROR test names
    failed = set(re.findall(r'(?:FAILED|ERROR) (\S+?)(?: |$)', vs))
    failed |= set(re.findall(r'FAIL: (\S+) \(', vs))
    failed |= set(re.findall(r'ERROR: (\S+) \(', vs))
    steps = (d.get('rollout') or {}).get('trace', {}).get('steps') or []
    agent_cmds = []
    for s in steps:
        if s.get('source') != 'agent':
            continue
        for tc in (s.get('tool_calls') or []):
            agent_cmds.append((tc.get('arguments') or {}).get('command', ''))
    # was any failing test name mentioned in an agent command?
    mentioned = set()
    for f in failed:
        fname = f.split('::')[-1] if '::' in f else f
        for c in agent_cmds:
            if fname and fname in c:
                mentioned.add(f)
                break
    print(f"{task:44s} failed={len(failed)} agent_ran_or_named={len(mentioned)}")
    for f in sorted(failed)[:8]:
        print("    ", f[:110], "  <- agent touched" if f in mentioned else "")
