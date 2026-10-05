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

FAILING = [
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667",
]

# Per failing task: how much time/steps was burned on the edit-application struggle?
# Count: git apply attempts that failed with 'unrecognized input', python - << PY patch attempts.
for task in FAILING:
    d = load(task)
    steps = (d.get('rollout') or {}).get('trace', {}).get('steps') or []
    n_apply_fail = 0
    n_pypatch = 0
    n_test_fail_127 = 0
    n_dupe_diff = 0
    cmds = []
    for s in steps:
        if s.get('source') != 'agent':
            continue
        for tc in (s.get('tool_calls') or []):
            c = (tc.get('arguments') or {}).get('command', '')
            obs, rc = obs_of(s)
            cmds.append(c)
            if 'git apply' in c and isinstance(rc, int) and rc != 0:
                n_apply_fail += 1
            if c.startswith('python') and 'PY' in c and ('p.read_text()' in c or '.replace(' in c):
                n_pypatch += 1
    # count repeated git --no-pager diff in last 6 cmds
    n_dupe_diff = sum(1 for c in cmds[-6:] if 'git --no-pager diff' in c or 'git --no-pager show' in c)
    print(f"{task:44s} apply_fail={n_apply_fail} py_patch={n_pypatch} tail_diff={n_dupe_diff} ncmds={len(cmds)}")
