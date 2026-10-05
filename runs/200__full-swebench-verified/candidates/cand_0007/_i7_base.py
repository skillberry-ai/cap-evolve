import json, os
d = json.load(open('_baseline.json'))
val = d['val']
print('reward', val['reward'])
for t in val['per_task']:
    print(f"{t['task_id']:45s} r={t['reward']:.2f} {t['feedback'][:60]}")
