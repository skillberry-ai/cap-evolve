import json, os, sys

TR = "trajectories"

def peek(name):
    d = json.load(open(os.path.join(TR, name)))
    print("== ", name, type(d).__name__)
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, (list, dict, str)):
                print("   ", k, type(v).__name__, len(v))
            else:
                print("   ", k, repr(v)[:100])

if __name__ == "__main__":
    for n in sys.argv[1:]:
        peek(n)
