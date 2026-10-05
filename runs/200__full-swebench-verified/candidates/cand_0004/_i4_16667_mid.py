import json, os

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

# django__django-16667: after pip install asgiref pytest, which python ran and where did django come from?
d = load('django__django-16667')
steps = (d.get('rollout') or {}).get('trace', {}).get('steps') or []
for i, s in enumerate(steps):
    if s.get('source') != 'agent':
        continue
    for tc in (s.get('tool_calls') or []):
        c = (tc.get('arguments') or {}).get('command', '')
        obs, rc = obs_of(s)
        if i >= 12 and i <= 21:
            print(f"--- step {i} rc={rc}: {c[:200]}")
            for l in (obs or '').splitlines()[:14]:
                print("   |", l[:170])
            print()
