import json, sys

def walk(o, prefix='', depth=0, maxdepth=4):
    if depth > maxdepth:
        return
    if isinstance(o, dict):
        for k, v in list(o.items())[:25]:
            if isinstance(v, (list, dict)):
                print(f'{prefix}{k}: {type(v).__name__} (len {len(v)})')
                walk(v, prefix + '  ', depth + 1, maxdepth)
            else:
                s = repr(v)
                print(f'{prefix}{k}: {s[:100]}')
    elif isinstance(o, list) and o:
        print(f'{prefix}[0] of {len(o)}:')
        walk(o[0], prefix + '  ', depth + 1, maxdepth)

fn = sys.argv[1] if len(sys.argv) > 1 else './trajectories/django__django-10554__cand_0002__t0.json'
d = json.load(open(fn))
walk(d)
