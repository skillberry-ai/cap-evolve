import json, os

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
TRAJ = os.path.join(BASE, "trajectories")

fn = os.path.join(TRAJ, "astropy__astropy-13453__cand_0002__t0.json")
d = json.load(open(fn))
print("input type:", type(d.get("input")))
inp = d.get("input")
if isinstance(inp, dict):
    print("input keys:", list(inp.keys()))
    for k, v in inp.items():
        if isinstance(v, str):
            print(f"--- {k} ({len(v)} chars) ---")
            print(v[:3500])
        else:
            print(f"--- {k}:", json.dumps(v)[:500])
