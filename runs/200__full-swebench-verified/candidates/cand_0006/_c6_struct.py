import json, os, glob

TRAJ = "trajectories"

def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

d = load("astropy__astropy-13453")
steps = ((d.get("rollout") or {}).get("output") or {}).get("steps") or []
print("N steps:", len(steps))
for idx, s in enumerate(steps[:6]):
    print(f"--- idx {idx} source={s.get('source')} role={s.get('role')} keys={sorted(s.keys())}")
    m = s.get("message")
    if m:
        print("  message head:", repr(m[:150]))
    ob = s.get("observation")
    if ob:
        print("  observation:", json.dumps(ob)[:600])
