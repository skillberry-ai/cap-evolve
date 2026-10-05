import json, os

BASE = "/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_swebench-harnessfix-s1/work/cand_0004"
TRAJ = os.path.join(BASE, "trajectories")

fn = os.path.join(TRAJ, "astropy__astropy-13453__cand_0002__t0.json")
d = json.load(open(fn))
steps = d["rollout"]["output"]["steps"]
# look at observation structure and message contents
for i, s in enumerate(steps[:8]):
    m = s.get("message") or {}
    print("=== step", i, "source:", s.get("source"))
    if isinstance(m, dict):
        print("  msg keys:", list(m.keys()))
        role = m.get("role")
        content = m.get("content")
        if isinstance(content, str):
            print("  content[:200]:", content[:200])
        elif isinstance(content, list):
            for c in content[:3]:
                print("  content part:", json.dumps(c)[:300])
        tcs = m.get("tool_calls")
        if tcs:
            for tc in tcs:
                print("  tool:", json.dumps(tc)[:300])
    else:
        print("  msg:", str(m)[:300])
