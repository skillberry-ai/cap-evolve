import json, os, sys

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

# Detailed dump of ONE failing task's commands + observation tails.
task = sys.argv[1] if len(sys.argv) > 1 else 'django__django-16667'
d = load(task)
steps = (d.get('rollout') or {}).get('trace', {}).get('steps') or []
print("TASK", task, "steps:", len(steps))
for i, s in enumerate(steps):
    if s.get('source') != 'agent':
        continue
    for tc in (s.get('tool_calls') or []):
        c = (tc.get('arguments') or {}).get('command', '')
        obs, rc = obs_of(s)
        tail = (obs or '')[-700:]
        print("=" * 90)
        print(f"--- step {i} rc={rc}: {c[:300]}")
        for l in tail.splitlines()[-14:]:
            print("  |", l[:190])
