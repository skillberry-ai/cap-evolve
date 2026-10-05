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

# 1) How many tasks (failing AND passing) attempted `git apply -p0 << 'PATCH'` with the
#    "*** Begin Patch" format (LLM-invented; git does not understand it)?
ALL = [f.replace('__cand_0002__t0.json', '') for f in sorted(os.listdir(TRAJ)) if f.endswith('.json')]
counts = dict(beginputch=0, tasks_beginputch=0, heredoc_std=0, tasks_heredoc_std=0)
task_detail = {}
for t in ALL:
    d = load(t)
    if not d or not d.get('rollout'):
        continue
    steps = ((d.get('rollout') or {}).get('trace') or {}).get('steps') or []
    bp = hs = 0
    for s in steps:
        if s.get('source') != 'agent':
            continue
        for tc in (s.get('tool_calls') or []):
            c = (tc.get('arguments') or {}).get('command', '')
            if '*** Begin Patch' in c:
                bp += 1
            if re.search(r"git apply( -p\d)? << ?'(\w+)'", c) and '***' not in c:
                hs += 1
    task_detail[t] = (bp, hs)
    counts['beginputch'] += bp
    if bp:
        counts['tasks_beginputch'] += 1
    counts['heredoc_std'] += hs
    if hs:
        counts['tasks_heredoc_std'] += 1

print(counts)
FAILING = set([
    "astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
    "django__django-12708","django__django-14007","django__django-14376","django__django-15629",
    "django__django-16032","django__django-16667",
])
for t, (bp, hs) in sorted(task_detail.items()):
    if bp:
        mark = 'FAIL' if t in FAILING else 'pass'
        print(f"{mark} {t:44s} beginputch={bp}")
