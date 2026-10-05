import json, os, re

TRAJ = "trajectories"

def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None

# KEY QUESTION: how does the verifier run tests per repo? Extract the run command
# from each task's verifier stdout (look after 'set +x').
import collections
cmds = collections.defaultdict(set)
for f in sorted(os.listdir(TRAJ)):
    if not f.endswith('.json'):
        continue
    d = json.load(open(os.path.join(TRAJ, f)))
    task = f.split('__')[0] + '/' + f.split('__')[1].split('.json')[0].replace(f.split('__')[1].split('.')[0], '')
    task = f.rsplit('__', 2)[0]
    repo = task.split('__')[0].split('/')[0] if '/' in task else task.split('-')[0]
    meta = ((d.get("rollout") or {}).get("metadata")) or {}
    vs = meta.get("verifier_stdout", "") or ""
    reward = (d.get("score") or {}).get("reward")
    # The actual test command appears right before test output. Search for known runners.
    for pat in [r"(\./tests/runtests\.py[^\n']*)", r"(python tests/runtests\.py[^\n']*)",
                r"(python -m pytest[^\n']*)", r"(pytest [^\n']{0,80})",
                r"(bin/py\.test[^\n']*)", r"(python runtests\.py[^\n']*)",
                r"(python -m pytest [^\n']*)"]:
        for m in re.finditer(pat, vs):
            cmds[task].add(m.group(1)[:100])
for t in sorted(cmds):
    print(t)
    for c in sorted(cmds[t])[:4]:
        print("   ", c)
