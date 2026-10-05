import json

d = json.load(open('trajectories/django__django-10554__seed__t0.json'))
r = d['rollout']
out = r['output']
def walk(o, path="", depth=0):
    if depth > 3:
        return
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, (dict, list)):
                print(f"{path}.{k}: {type(v).__name__} len={len(v)}")
                walk(v, f"{path}.{k}", depth+1)
            else:
                s = str(v)
                print(f"{path}.{k}: {s[:120]}")
    elif isinstance(o, list):
        print(f"{path}: list len={len(o)}")
walk(out)
print()
print("=== TOOL_CALLS (top-level rollout) ===")
for tc in (r.get('tool_calls') or [])[:5]:
    print(json.dumps(tc)[:300])
print("n tool_calls:", len(r.get('tool_calls') or []))
print()
print("=== NOTES ===")
print(json.dumps(r.get('trace', {}).get('notes'))[:500])
print()
print("=== final_metrics ===")
print(json.dumps(r.get('trace', {}).get('final_metrics'))[:500])
