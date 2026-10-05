import json, sys, os

TRAJ = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s2/work/cand_0004/trajectories"

def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            walk(v, path + "/" + k)
    elif isinstance(o, list):
        print(path, "LIST len", len(o))
        if o:
            walk(o[0], path + "[0]")
    else:
        s = str(o)
        print(path, "=", s[:120].replace("\n", "|"))

if __name__ == "__main__":
    f = sys.argv[1] if len(sys.argv) > 1 else os.path.join(TRAJ, "django__django-10554__seed__t0.json")
    data = json.load(open(f))
    walk(data)
