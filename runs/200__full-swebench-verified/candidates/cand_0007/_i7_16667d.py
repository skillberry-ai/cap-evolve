import json, os

TRAJ = "trajectories"
d = json.load(open(os.path.join(TRAJ, "django__django-16667__cand_0002__t0.json")))
steps = d["rollout"]["output"]["steps"]
# print the observation keys of steps 17-20 to see full structure
for idx in (17, 18, 19, 20):
    s = steps[idx]
    obs = s.get("observation") or {}
    try:
        c = obs["results"][0]["content"]
        j = json.loads(c)
        print(f"@{idx}: rc={j.get('returncode')} keys={sorted(j.keys())}")
        for k in j:
            if k not in ("returncode", "output_head", "output_tail", "output"):
                print("   ", k, "=", str(j[k])[:100])
    except Exception as e:
        print(f"@{idx}: obs parse error {e}")
    for tc in (s.get("tool_calls") or []):
        print("   CMD:", (tc.get("arguments") or {}).get("command", "")[:150])
