import json, os

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
TRAJ = os.path.join(BASE, "trajectories")

fn = os.path.join(TRAJ, "astropy__astropy-13453__cand_0002__t0.json")
d = json.load(open(fn))
print("top keys:", list(d.keys()))
roll = d.get("rollout") or {}
print("rollout keys:", list(roll.keys()))
out = roll.get("output") or {}
print("output keys:", list(out.keys()))
steps = out.get("steps") or []
print("n steps:", len(steps))
if steps:
    s0 = steps[0]
    print("step keys:", list(s0.keys()))
    print("step0 source:", s0.get("source"))
    # print agent messages structure
    for s in steps[:4]:
        print("---")
        print("source:", s.get("source"))
        if s.get("role"):
            print("role:", s.get("role"))
        txt = s.get("content") or s.get("text") or ""
        if isinstance(txt, str):
            print("content[:300]:", txt[:300])
        tcs = s.get("tool_calls") or []
        for tc in tcs:
            print("tool_call:", json.dumps(tc)[:400])
