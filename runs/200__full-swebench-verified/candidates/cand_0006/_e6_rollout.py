import json, os, sys

fn = sys.argv[1] if len(sys.argv) > 1 else 'trajectories/django__django-10554__cand_0002__t0.json'
d = json.load(open(fn))
r = d['rollout']
print('task_id:', r['task_id'])
print('error:', r.get('error'))
print('cost:', r.get('cost_usd'), 'tokens:', r.get('tokens'))
out = r.get('output') or {}
print('output keys:', list(out.keys()) if isinstance(out, dict) else type(out))
if isinstance(out, dict):
    for k, v in out.items():
        s = json.dumps(v)[:300] if not isinstance(v, str) else v[:300]
        print(f'--- output.{k} ---')
        print(s)
tc = r.get('tool_calls')
print('tool_calls:', type(tc), len(tc) if hasattr(tc, '__len__') else tc)
tr = r.get('trace')
print('trace:', type(tr), len(tr) if hasattr(tr, '__len__') else tr)
md = r.get('metadata') or {}
print('metadata keys:', list(md.keys()))
for k, v in md.items():
    s = json.dumps(v)[:200] if not isinstance(v, str) else v[:200]
    print(f'--- meta.{k} ---: {s}')
print('=== score ===')
print(json.dumps(d['score'], indent=1)[:1500])
