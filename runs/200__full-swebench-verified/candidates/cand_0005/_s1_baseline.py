import subprocess, json

r = subprocess.run(['git', 'show', '8617c6b:baseline.json'], capture_output=True, text=True)
d = json.loads(r.stdout)
for split in d:
    print(split, 'reward', d[split].get('reward'))
    per = d[split].get('per_task') or []
    fails = [(t['task_id'], t.get('reward')) for t in per if (t.get('reward') or 0) < 0.5]
    print(len(per), 'tasks;', len(fails), 'failing:')
    for f in fails:
        print('  ', f)
