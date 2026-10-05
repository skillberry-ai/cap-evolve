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

# How does the VERIFIER invoke tests for django tasks? Print lines before 'Testing against Django'
for task in ['django__django-16667', 'django__django-10554', 'astropy__astropy-13453']:
    d = load(task)
    meta = ((d.get('rollout') or {}).get('metadata')) or {}
    vs = meta.get('verifier_stdout', '') or ''
    print("=" * 90)
    print(task)
    # find the segment between 'git apply' and first 'Testing against' / first test output
    lines = vs.splitlines()
    for i, l in enumerate(lines):
        if 'runtests' in l or 'python -m' in l or 'tox' in l or 'conda' in l.lower() or '.py' in l and i < 30:
            print(f"  {i}: {l[:170]}")
    print("  --- context around 'SWEBench results':")
    for i, l in enumerate(lines):
        if 'SWEBench results' in l:
            for j in range(max(0, i-3), min(len(lines), i+3)):
                print(f"   {j}: {lines[j][:170]}")
