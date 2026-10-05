import json, os
fn = 'trajectories/django__django-10554__cand_0002__t0.json'
d = json.load(open(fn))
def walk(o, path='', depth=0):
    if depth > 5: return
    if isinstance(o, dict):
        for k in o:
            walk(o[k], path + '/' + k, depth+1)
    elif isinstance(o, list):
        print(f"{path} [list len {len(o)}]")
        if o: walk(o[0], path + '[0]', depth+1)
    else:
        s = str(o)
        print(f"{path} = {s[:60]}")
walk(d)
