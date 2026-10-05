import json, sys, os

# Show raw observation content for a given step_id (no head/tail merge).
d = json.load(open(sys.argv[1]))
sid = int(sys.argv[2])
r = d['rollout']
for s in r['output']['steps']:
    if s.get('step_id') == sid:
        obs = s.get('observation') or {}
        for rr in (obs.get('results') or []):
            print(rr.get('content', '')[:int(sys.argv[3]) if len(sys.argv) > 3 else 4000])
