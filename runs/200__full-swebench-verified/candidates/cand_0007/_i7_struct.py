import json, os, glob

TRAJ = "trajectories"

# Inspect structure of one trajectory file
p = os.path.join(TRAJ, "django__django-10554__cand_0002__t0.json")
d = json.load(open(p))

def walk(o, prefix="", depth=0):
    if depth > 4:
        return
    if isinstance(o, dict):
        for k, v in list(o.items())[:12]:
            t = type(v).__name__
            if isinstance(v, (dict, list)):
                print(f"{prefix}{k}: {t} len={len(v)}")
                walk(v, prefix + "  ", depth + 1)
            else:
                s = str(v)[:100].replace("\n", " ")
                print(f"{prefix}{k}: {t} = {s}")
    elif isinstance(o, list):
        for i, v in enumerate(o[:2]):
            print(f"{prefix}[{i}]:")
            walk(v, prefix + "  ", depth + 1)

walk(d)
