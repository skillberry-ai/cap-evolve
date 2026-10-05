import json, sys

fn = sys.argv[1] if len(sys.argv) > 1 else 'trajectories/django__django-10554__seed__t0.json'
d = json.load(open(fn))

def walk(o, depth=0, maxdepth=3):
    if depth > maxdepth:
        return
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, (dict, list)):
                print('  ' * depth + k, type(v).__name__, 'len=%d' % len(v))
                walk(v, depth + 1, maxdepth)
            else:
                s = str(v)
                print('  ' * depth + k, type(v).__name__, s[:100])
    elif isinstance(o, list):
        print('  ' * depth + '[list len=%d]' % len(o))
        if o:
            walk(o[0], depth + 1, maxdepth)

walk(d)
