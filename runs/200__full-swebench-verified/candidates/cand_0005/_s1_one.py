import json, os, sys

fn = sys.argv[1]
d = json.load(open(fn))
ro = d['rollout']
print('== input ==')
print(json.dumps(d['input'])[:2000])
print()
print('== rollout.output keys ==', list((ro.get('output') or {}).keys()))
out = ro.get('output') or {}
for k, v in out.items():
    if isinstance(v, str):
        print(f'-- output.{k} (len {len(v)}):')
        print(v[:800])
    else:
        print(f'-- output.{k}:', json.dumps(v)[:500])
print()
sc = d['score']
print('== score ==')
print('reward:', sc.get('reward'), 'n:', sc.get('n'))
print('feedback:', str(sc.get('feedback'))[:1500])
print('raw:', str(sc.get('raw'))[:800])
